// lib/screens/admin_dashboard_screen.dart

import 'package:flutter/material.dart';

import '../services/admin_api_service.dart';

class AdminDashboardScreen extends StatefulWidget {
  const AdminDashboardScreen({super.key});

  @override
  State<AdminDashboardScreen> createState() => _AdminDashboardScreenState();
}

class _AdminDashboardScreenState extends State<AdminDashboardScreen> {
  final AdminApiService _service = AdminApiService();

  late Future<List<AdminCommandItem>> _future;

  AdminSeasonInfo? _seasonInfo;
  int? _selectedSeason;
  bool _savingSeason = false;

  String? _runningKey;
  Map<String, dynamic>? _lastResult;
  String? _error;

  @override
  void initState() {
    super.initState();
    _future = _service.fetchCommands();
    _loadSeason();
  }

  Future<void> _loadSeason() async {
    try {
      final info = await _service.fetchSeason();

      if (!mounted) return;

      setState(() {
        _seasonInfo = info;
        _selectedSeason = info.activeSeason;
      });
    } catch (error) {
      if (!mounted) return;

      setState(() {
        _error = error.toString();
      });
    }
  }

  Future<void> _saveSeason() async {
    final season = _selectedSeason;

    if (season == null) return;

    setState(() {
      _savingSeason = true;
      _error = null;
    });

    try {
      final info = await _service.saveSeason(season);

      if (!mounted) return;

      setState(() {
        _seasonInfo = info;
        _selectedSeason = info.activeSeason;
        _future = _service.fetchCommands();
        _savingSeason = false;
      });
    } catch (error) {
      if (!mounted) return;

      setState(() {
        _error = error.toString();
        _savingSeason = false;
      });
    }
  }

  Future<void> _run(AdminCommandItem item) async {
    setState(() {
      _runningKey = item.key;
      _lastResult = null;
      _error = null;
    });

    try {
      final result = await _service.runCommand(item.key);

      if (!mounted) return;

      setState(() {
        _lastResult = result;
        _runningKey = null;
      });
    } catch (error) {
      if (!mounted) return;

      setState(() {
        _error = error.toString();
        _runningKey = null;
      });
    }
  }

  void _refresh() {
    setState(() {
      _future = _service.fetchCommands();
      _lastResult = null;
      _error = null;
    });

    _loadSeason();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Admin Command Center'),
        actions: [
          IconButton(
            onPressed: _runningKey == null ? _refresh : null,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: FutureBuilder<List<AdminCommandItem>>(
        future: _future,
        builder: (context, snapshot) {
          final commands = snapshot.data ?? [];

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(
                'Safe approved automations',
                style: theme.textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Choose the active season, then run approved backend CLI workflows.',
                style: theme.textTheme.bodyMedium,
              ),
              const SizedBox(height: 16),
              _SeasonCard(
                seasonInfo: _seasonInfo,
                selectedSeason: _selectedSeason,
                saving: _savingSeason,
                disabled: _runningKey != null,
                onChanged: (value) {
                  setState(() {
                    _selectedSeason = value;
                  });
                },
                onSave: _saveSeason,
              ),
              const SizedBox(height: 16),
              if (snapshot.connectionState == ConnectionState.waiting)
                const Center(
                  child: Padding(
                    padding: EdgeInsets.all(24),
                    child: CircularProgressIndicator(),
                  ),
                )
              else if (snapshot.hasError)
                _ErrorView(
                  message: snapshot.error.toString(),
                  onRetry: _refresh,
                )
              else ...[
                for (final entry in _groupCommands(commands).entries) ...[
                  Padding(
                    padding: const EdgeInsets.only(top: 10, bottom: 8),
                    child: Text(
                      entry.key,
                      style: theme.textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  for (final item in entry.value) ...[
                    _CommandCard(
                      item: item,
                      isRunning: _runningKey == item.key,
                      disabled: _runningKey != null,
                      onRun: () => _run(item),
                    ),
                    const SizedBox(height: 12),
                  ],
                ],
              ],
              if (_error != null) ...[
                const SizedBox(height: 16),
                _ResultPanel(
                  title: 'Error',
                  text: _error!,
                  isError: true,
                ),
              ],
              if (_lastResult != null) ...[
                const SizedBox(height: 16),
                _ResultPanel(
                  title: 'Last Run Result',
                  text: _formatResult(_lastResult!),
                  isError: _lastResult!['ok'] != true,
                ),
              ],
            ],
          );
        },
      ),
    );
  }

  Map<String, List<AdminCommandItem>> _groupCommands(
    List<AdminCommandItem> commands,
  ) {
    final grouped = <String, List<AdminCommandItem>>{};

    for (final command in commands) {
      grouped.putIfAbsent(command.category, () => []);
      grouped[command.category]!.add(command);
    }

    return grouped;
  }

  String _formatResult(Map<String, dynamic> result) {
    final buffer = StringBuffer();

    buffer.writeln('OK: ${result['ok']}');
    buffer.writeln('Command: ${result['label'] ?? result['key']}');
    buffer.writeln('Category: ${result['category'] ?? 'General'}');
    buffer.writeln('Duration: ${result['duration_seconds']} seconds');

    final results = (result['results'] as List?) ?? [];

    for (final rawStep in results) {
      final step = rawStep as Map<String, dynamic>;

      buffer.writeln('');
      buffer.writeln('==============================');
      buffer.writeln('STEP ${step['step']}');
      buffer.writeln('==============================');
      buffer.writeln(step['command']);
      buffer.writeln('Return code: ${step['return_code']}');
      buffer.writeln('Duration: ${step['duration_seconds']} seconds');

      final stdout = (step['stdout'] ?? '').toString().trim();
      final stderr = (step['stderr'] ?? '').toString().trim();
      final error = (step['error'] ?? '').toString().trim();

      if (stdout.isNotEmpty) {
        buffer.writeln('');
        buffer.writeln('STDOUT:');
        buffer.writeln(stdout);
      }

      if (stderr.isNotEmpty) {
        buffer.writeln('');
        buffer.writeln('STDERR:');
        buffer.writeln(stderr);
      }

      if (error.isNotEmpty) {
        buffer.writeln('');
        buffer.writeln('ERROR:');
        buffer.writeln(error);
      }
    }

    return buffer.toString();
  }
}

class _SeasonCard extends StatelessWidget {
  final AdminSeasonInfo? seasonInfo;
  final int? selectedSeason;
  final bool saving;
  final bool disabled;
  final ValueChanged<int?> onChanged;
  final VoidCallback onSave;

  const _SeasonCard({
    required this.seasonInfo,
    required this.selectedSeason,
    required this.saving,
    required this.disabled,
    required this.onChanged,
    required this.onSave,
  });

  @override
  Widget build(BuildContext context) {
    final seasons = seasonInfo?.availableSeasons ?? const <int>[2026];

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: LayoutBuilder(
          builder: (context, constraints) {
            final compact = constraints.maxWidth < 520;

            final dropdown = DropdownButtonFormField<int>(
              value: selectedSeason,
              decoration: const InputDecoration(
                labelText: 'Active Season',
                border: OutlineInputBorder(),
              ),
              items: seasons
                  .map(
                    (season) => DropdownMenuItem<int>(
                      value: season,
                      child: Text(season.toString()),
                    ),
                  )
                  .toList(),
              onChanged: disabled ? null : onChanged,
            );

            final saveButton = FilledButton.icon(
              onPressed: saving || disabled ? null : onSave,
              icon: saving
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.save),
              label: const Text('Save Season'),
            );

            if (compact) {
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Row(
                    children: [
                      Icon(Icons.event),
                      SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          'Season Control',
                          style: TextStyle(fontWeight: FontWeight.bold),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  dropdown,
                  const SizedBox(height: 12),
                  SizedBox(
                    width: double.infinity,
                    child: saveButton,
                  ),
                ],
              );
            }

            return Row(
              children: [
                const Icon(Icons.event),
                const SizedBox(width: 12),
                const Text(
                  'Season Control',
                  style: TextStyle(fontWeight: FontWeight.bold),
                ),
                const SizedBox(width: 16),
                Expanded(child: dropdown),
                const SizedBox(width: 12),
                saveButton,
              ],
            );
          },
        ),
      ),
    );
  }
}

class _CommandCard extends StatelessWidget {
  final AdminCommandItem item;
  final bool isRunning;
  final bool disabled;
  final VoidCallback onRun;

  const _CommandCard({
    required this.item,
    required this.isRunning,
    required this.disabled,
    required this.onRun,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.admin_panel_settings_outlined),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    item.label,
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                Chip(label: Text(item.apiSafeLevel.toUpperCase())),
              ],
            ),
            const SizedBox(height: 8),
            Text(item.description),
            const SizedBox(height: 10),
            for (final step in item.steps)
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Text(
                  step,
                  style: theme.textTheme.bodySmall?.copyWith(
                    fontFamily: 'monospace',
                  ),
                ),
              ),
            const SizedBox(height: 10),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: disabled ? null : onRun,
                icon: isRunning
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.play_arrow),
                label: Text(isRunning ? 'Running...' : 'Run'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ResultPanel extends StatelessWidget {
  final String title;
  final String text;
  final bool isError;

  const _ResultPanel({
    required this.title,
    required this.text,
    required this.isError,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Card(
      color: isError ? colorScheme.errorContainer : null,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: 10),
            SelectableText(
              text,
              style: const TextStyle(
                fontFamily: 'monospace',
                fontSize: 12,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const _ErrorView({
    required this.message,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, size: 42),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 12),
            FilledButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }
}