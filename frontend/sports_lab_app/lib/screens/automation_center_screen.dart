// lib/screens/automation_center_screen.dart

import 'package:flutter/material.dart';

import '../services/automation_api_service.dart';

class AutomationCenterScreen extends StatefulWidget {
  const AutomationCenterScreen({super.key});

  @override
  State<AutomationCenterScreen> createState() => _AutomationCenterScreenState();
}

class _AutomationCenterScreenState extends State<AutomationCenterScreen> {
  final AutomationApiService _api = AutomationApiService();

  bool _loading = true;
  bool _running = false;
  String? _error;
  List<AutomationJobItem> _jobs = [];
  List<AutomationRunItem> _history = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      await _api.seedJobs();

      final jobs = await _api.fetchJobs();
      final history = await _api.fetchHistory();

      if (!mounted) return;

      setState(() {
        _jobs = jobs;
        _history = history;
      });
    } catch (e) {
      if (!mounted) return;

      setState(() {
        _error = e.toString();
      });
    } finally {
      if (!mounted) return;

      setState(() {
        _loading = false;
      });
    }
  }

  Future<void> _runJob(AutomationJobItem job) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: Text('Run ${job.title}?'),
          content: const Text(
            'This may run API ingestion, odds refresh, predictions, grouping, training or backtests depending on the job.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Run Now'),
            ),
          ],
        );
      },
    );

    if (confirmed != true) return;

    setState(() {
      _running = true;
      _error = null;
    });

    try {
      await _api.runJob(job.jobKey);
      await _load();

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${job.title} completed.')),
      );
    } catch (e) {
      if (!mounted) return;

      setState(() {
        _error = e.toString();
      });
    } finally {
      if (!mounted) return;

      setState(() {
        _running = false;
      });
    }
  }

  Future<void> _toggleJob(AutomationJobItem job) async {
    try {
      await _api.setEnabled(
        jobKey: job.jobKey,
        enabled: !job.enabled,
      );

      await _load();
    } catch (e) {
      if (!mounted) return;

      setState(() {
        _error = e.toString();
      });
    }
  }

  Color _statusColor(String status) {
    switch (status.toLowerCase()) {
      case 'success':
        return Colors.green;
      case 'failed':
        return Colors.red;
      case 'running':
        return Colors.orange;
      default:
        return Colors.blueGrey;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FB),
      appBar: AppBar(
        title: const Text('Automation Center'),
        actions: [
          IconButton(
            onPressed: _running ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  _HeaderCard(running: _running),
                  const SizedBox(height: 14),
                  if (_error != null) ...[
                    _ErrorCard(error: _error!),
                    const SizedBox(height: 14),
                  ],
                  Text(
                    'Scheduled Jobs',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w900,
                        ),
                  ),
                  const SizedBox(height: 10),
                  for (final job in _jobs) ...[
                    _JobCard(
                      job: job,
                      statusColor: _statusColor(job.lastStatus),
                      onRun: _running ? null : () => _runJob(job),
                      onToggle: _running ? null : () => _toggleJob(job),
                    ),
                    const SizedBox(height: 10),
                  ],
                  const SizedBox(height: 16),
                  Text(
                    'Recent Runs',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w900,
                        ),
                  ),
                  const SizedBox(height: 10),
                  if (_history.isEmpty)
                    const _EmptyHistoryCard()
                  else
                    for (final run in _history.take(20)) ...[
                      _RunCard(
                        run: run,
                        statusColor: _statusColor(run.status),
                      ),
                      const SizedBox(height: 8),
                    ],
                ],
              ),
            ),
    );
  }
}

class _HeaderCard extends StatelessWidget {
  final bool running;

  const _HeaderCard({
    required this.running,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: const Color(0xFF0F172A),
        borderRadius: BorderRadius.circular(24),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.schedule_outlined,
            color: Colors.white,
            size: 34,
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  running ? 'Automation job running...' : 'Remote Automation Ready',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w900,
                      ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Backend jobs run on the server even when the APK is closed.',
                  style: TextStyle(
                    color: Colors.white.withOpacity(0.78),
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _JobCard extends StatelessWidget {
  final AutomationJobItem job;
  final Color statusColor;
  final VoidCallback? onRun;
  final VoidCallback? onToggle;

  const _JobCard({
    required this.job,
    required this.statusColor,
    required this.onRun,
    required this.onToggle,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 0,
      color: Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: BorderSide(color: Colors.black.withOpacity(0.06)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  job.enabled ? Icons.play_circle_outline : Icons.pause_circle_outline,
                  color: job.enabled ? Colors.green : Colors.grey,
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    job.title,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w900,
                        ),
                  ),
                ),
                Chip(
                  label: Text(
                    job.lastStatus,
                    style: const TextStyle(color: Colors.white),
                  ),
                  backgroundColor: statusColor,
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text('Cron: ${job.cronExpression}'),
            Text('Next run: ${job.nextRunAt ?? '-'}'),
            Text('Last run: ${job.lastRunAt ?? '-'}'),
            const SizedBox(height: 12),
            Row(
              children: [
                FilledButton.icon(
                  onPressed: onRun,
                  icon: const Icon(Icons.flash_on_outlined),
                  label: const Text('Run Now'),
                ),
                const SizedBox(width: 10),
                OutlinedButton.icon(
                  onPressed: onToggle,
                  icon: Icon(job.enabled ? Icons.pause : Icons.play_arrow),
                  label: Text(job.enabled ? 'Disable' : 'Enable'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _RunCard extends StatelessWidget {
  final AutomationRunItem run;
  final Color statusColor;

  const _RunCard({
    required this.run,
    required this.statusColor,
  });

  @override
  Widget build(BuildContext context) {
    final progress = (run.progressPercent / 100).clamp(0.0, 1.0);

    return Card(
      elevation: 0,
      color: Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: BorderSide(color: Colors.black.withOpacity(0.05)),
      ),
      child: ExpansionTile(
        leading: CircleAvatar(
          backgroundColor: statusColor.withOpacity(0.12),
          child: Icon(
            run.status == 'success'
                ? Icons.check
                : run.status == 'failed'
                    ? Icons.close
                    : run.status == 'interrupted'
                        ? Icons.warning_amber
                        : Icons.timelapse,
            color: statusColor,
          ),
        ),
        title: Text(
          run.title,
          style: const TextStyle(fontWeight: FontWeight.w800),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Status: ${run.status}'),
            Text('Started: ${run.startedAt ?? '-'}'),
            Text('Duration: ${run.durationSeconds?.toStringAsFixed(1) ?? '-'} sec'),
            const SizedBox(height: 6),
            LinearProgressIndicator(value: progress),
            const SizedBox(height: 4),
            Text('${run.progressPercent.toStringAsFixed(1)}% • ${run.currentStep ?? '-'}'),
            if (run.error != null && run.error!.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(
                run.error!,
                style: TextStyle(
                  color: Colors.red.shade700,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ],
        ),
        children: [
          if (run.commandLog.isEmpty)
            const Padding(
              padding: EdgeInsets.all(14),
              child: Text('No command logs saved for this run.'),
            )
          else
            for (final item in run.commandLog)
              Padding(
                padding: const EdgeInsets.fromLTRB(14, 6, 14, 10),
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: const Color(0xFFF8FAFC),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: Colors.black.withOpacity(0.06)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '#${item.index} • ${item.status}',
                        style: TextStyle(
                          fontWeight: FontWeight.w900,
                          color: item.status == 'success'
                              ? Colors.green.shade700
                              : item.status == 'failed'
                                  ? Colors.red.shade700
                                  : Colors.orange.shade700,
                        ),
                      ),
                      const SizedBox(height: 6),
                      SelectableText(
                        item.command,
                        style: const TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 12,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text('Duration: ${item.durationSeconds?.toStringAsFixed(1) ?? '-'} sec'),
                      if (item.stdout.trim().isNotEmpty) ...[
                        const SizedBox(height: 8),
                        const Text(
                          'Output',
                          style: TextStyle(fontWeight: FontWeight.w800),
                        ),
                        SelectableText(
                          item.stdout,
                          style: const TextStyle(fontSize: 12),
                        ),
                      ],
                      if (item.stderr.trim().isNotEmpty) ...[
                        const SizedBox(height: 8),
                        Text(
                          'Error',
                          style: TextStyle(
                            fontWeight: FontWeight.w800,
                            color: Colors.red.shade700,
                          ),
                        ),
                        SelectableText(
                          item.stderr,
                          style: TextStyle(
                            fontSize: 12,
                            color: Colors.red.shade700,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
        ],
      ),
    );
  }
}


class _ErrorCard extends StatelessWidget {
  final String error;

  const _ErrorCard({
    required this.error,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      color: Colors.red.shade50,
      elevation: 0,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Text(
          error,
          style: TextStyle(
            color: Colors.red.shade900,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
    );
  }
}

class _EmptyHistoryCard extends StatelessWidget {
  const _EmptyHistoryCard();

  @override
  Widget build(BuildContext context) {
    return const Card(
      elevation: 0,
      child: Padding(
        padding: EdgeInsets.all(16),
        child: Text('No automation runs yet.'),
      ),
    );
  }
}