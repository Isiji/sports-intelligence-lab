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

  String _selectedCategory = 'All';
  String _selectedSafety = 'All';

  final List<_CommandHistoryItem> _history = [];

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

  Future<void> _runWithConfirmation(AdminCommandItem item) async {
    final requiresConfirmation = _requiresHeavyConfirmation(item);

    if (requiresConfirmation) {
      final confirmed = await _showHeavyCommandDialog(item);

      if (confirmed != true) return;
    }

    await _run(item);
  }

  Future<void> _run(AdminCommandItem item) async {
    setState(() {
      _runningKey = item.key;
      _lastResult = null;
      _error = null;
    });

    final startedAt = DateTime.now();

    try {
      final result = await _service.runCommand(item.key);

      if (!mounted) return;

      final success = result['ok'] == true;
      final duration = _doubleValue(result['duration_seconds']);
      final failedStep = _intValue(result['failed_step']);

      setState(() {
        _lastResult = result;
        _runningKey = null;
        _history.insert(
          0,
          _CommandHistoryItem(
            label: item.label,
            category: item.category,
            safety: item.apiSafeLevel,
            startedAt: startedAt,
            success: success,
            durationSeconds: duration,
            failedStep: failedStep,
          ),
        );
      });
    } catch (error) {
      if (!mounted) return;

      setState(() {
        _error = error.toString();
        _runningKey = null;
        _history.insert(
          0,
          _CommandHistoryItem(
            label: item.label,
            category: item.category,
            safety: item.apiSafeLevel,
            startedAt: startedAt,
            success: false,
            durationSeconds: null,
            failedStep: null,
            error: error.toString(),
          ),
        );
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

  Future<bool?> _showHeavyCommandDialog(AdminCommandItem item) {
    return showDialog<bool>(
      context: context,
      builder: (context) {
        final stepCount = item.steps.length;
        final timeoutMinutes = _estimatedTimeoutMinutes(item);

        return AlertDialog(
          icon: const Icon(Icons.warning_amber_rounded),
          title: Text('Run ${item.label}?'),
          content: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'This is a heavy workflow. It may:',
                  style: TextStyle(fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 12),
                const _DialogBullet(text: 'Consume API calls'),
                const _DialogBullet(text: 'Run long backend CLI jobs'),
                const _DialogBullet(text: 'Rebuild intelligence or features'),
                const _DialogBullet(text: 'Train models or run backtests'),
                const SizedBox(height: 12),
                Text('Steps: $stepCount'),
                if (timeoutMinutes != null) Text('Timeout: $timeoutMinutes min'),
                const SizedBox(height: 12),
                const Text(
                  'Only continue if you are ready to let this workflow run.',
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel'),
            ),
            FilledButton.icon(
              onPressed: () => Navigator.pop(context, true),
              icon: const Icon(Icons.play_arrow),
              label: const Text('Run Workflow'),
            ),
          ],
        );
      },
    );
  }

  bool _requiresHeavyConfirmation(AdminCommandItem item) {
    final safety = item.apiSafeLevel.toLowerCase().trim();
    final key = item.key.toLowerCase().trim();
    final label = item.label.toLowerCase().trim();

    if (safety == 'heavy') return true;

    if (key.contains('overnight')) return true;
    if (key.contains('train')) return true;
    if (key.contains('backtest')) return true;
    if (key.contains('research')) return true;

    if (label.contains('overnight')) return true;
    if (label.contains('train')) return true;
    if (label.contains('backtest')) return true;
    if (label.contains('research')) return true;

    return item.steps.length >= 8;
  }

  List<AdminCommandItem> _filteredCommands(List<AdminCommandItem> commands) {
    return commands.where((item) {
      final matchesCategory = _selectedCategory == 'All' || item.category == _selectedCategory;

      final safety = item.apiSafeLevel.toLowerCase().trim();
      final isHeavy = _requiresHeavyConfirmation(item);

      final matchesSafety = switch (_selectedSafety) {
        'All' => true,
        'Safe' => safety == 'safe' && !isHeavy,
        'Heavy' => isHeavy,
        _ => true,
      };

      return matchesCategory && matchesSafety;
    }).toList();
  }

  List<String> _categories(List<AdminCommandItem> commands) {
    final values = commands.map((item) => item.category).where((item) => item.trim().isNotEmpty).toSet().toList();

    values.sort();

    return ['All', ...values];
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

    final failedStep = result['failed_step'];

    if (failedStep != null) {
      buffer.writeln('Failed step: $failedStep');
    }

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
      buffer.writeln('OK: ${step['ok']}');

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

  int? _estimatedTimeoutMinutes(AdminCommandItem item) {
    if (item.steps.isEmpty) return null;

    if (item.key.contains('full_research')) return 300;
    if (item.key.contains('expanded')) return 240;
    if (item.key.contains('core_markets')) return 180;
    if (item.key.contains('train')) return 120;
    if (item.key.contains('overnight')) return 90;
    if (item.key.contains('diagnostics')) return 90;
    if (item.key.contains('intelligence')) return 120;

    if (item.steps.length >= 15) return 180;
    if (item.steps.length >= 10) return 120;
    if (item.steps.length >= 5) return 90;

    return 60;
  }

  double? _doubleValue(dynamic value) {
    if (value == null) return null;

    if (value is num) return value.toDouble();

    return double.tryParse(value.toString());
  }

  int? _intValue(dynamic value) {
    if (value == null) return null;

    if (value is int) return value;

    return int.tryParse(value.toString());
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Admin Command Center'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: _runningKey == null ? _refresh : null,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: FutureBuilder<List<AdminCommandItem>>(
        future: _future,
        builder: (context, snapshot) {
          final allCommands = snapshot.data ?? [];
          final filteredCommands = _filteredCommands(allCommands);
          final groupedCommands = _groupCommands(filteredCommands);
          final categories = _categories(allCommands);

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(
                'Admin Control Center',
                style: theme.textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Run approved backend workflows, manage the active season, and review recent command execution.',
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
                _AdminSummaryCards(
                  totalCommands: allCommands.length,
                  visibleCommands: filteredCommands.length,
                  runningKey: _runningKey,
                  historyCount: _history.length,
                ),
                const SizedBox(height: 16),
                _FilterPanel(
                  categories: categories,
                  selectedCategory: _selectedCategory,
                  selectedSafety: _selectedSafety,
                  disabled: _runningKey != null,
                  onCategoryChanged: (value) {
                    setState(() {
                      _selectedCategory = value;
                    });
                  },
                  onSafetyChanged: (value) {
                    setState(() {
                      _selectedSafety = value;
                    });
                  },
                ),
                const SizedBox(height: 16),
                if (filteredCommands.isEmpty)
                  const _EmptyCommandsView()
                else
                  for (final entry in groupedCommands.entries) ...[
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
                        requiresConfirmation: _requiresHeavyConfirmation(item),
                        estimatedTimeoutMinutes: _estimatedTimeoutMinutes(item),
                        onRun: () => _runWithConfirmation(item),
                      ),
                      const SizedBox(height: 12),
                    ],
                  ],
                if (_history.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  _HistoryPanel(
                    history: _history,
                    onClear: () {
                      setState(() {
                        _history.clear();
                      });
                    },
                  ),
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
              const SizedBox(height: 24),
            ],
          );
        },
      ),
    );
  }
}

class _AdminSummaryCards extends StatelessWidget {
  final int totalCommands;
  final int visibleCommands;
  final String? runningKey;
  final int historyCount;

  const _AdminSummaryCards({
    required this.totalCommands,
    required this.visibleCommands,
    required this.runningKey,
    required this.historyCount,
  });

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final compact = constraints.maxWidth < 760;

        final cards = [
          _SummaryCard(
            title: 'Commands',
            value: '$visibleCommands / $totalCommands',
            icon: Icons.terminal,
          ),
          _SummaryCard(
            title: 'Running',
            value: runningKey == null ? 'None' : 'Active',
            icon: runningKey == null ? Icons.check_circle_outline : Icons.sync,
          ),
          _SummaryCard(
            title: 'History',
            value: historyCount.toString(),
            icon: Icons.history,
          ),
        ];

        if (compact) {
          return Column(
            children: [
              for (final card in cards) ...[
                card,
                const SizedBox(height: 10),
              ],
            ],
          );
        }

        return Row(
          children: [
            for (final card in cards) ...[
              Expanded(child: card),
              if (card != cards.last) const SizedBox(width: 10),
            ],
          ],
        );
      },
    );
  }
}

class _SummaryCard extends StatelessWidget {
  final String title;
  final String value;
  final IconData icon;

  const _SummaryCard({
    required this.title,
    required this.value,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            Icon(icon),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                title,
                style: theme.textTheme.bodyMedium,
              ),
            ),
            Text(
              value,
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _FilterPanel extends StatelessWidget {
  final List<String> categories;
  final String selectedCategory;
  final String selectedSafety;
  final bool disabled;
  final ValueChanged<String> onCategoryChanged;
  final ValueChanged<String> onSafetyChanged;

  const _FilterPanel({
    required this.categories,
    required this.selectedCategory,
    required this.selectedSafety,
    required this.disabled,
    required this.onCategoryChanged,
    required this.onSafetyChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const _SectionTitle(
              icon: Icons.filter_list,
              title: 'Filters',
            ),
            const SizedBox(height: 12),
            Text(
              'Category',
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final category in categories)
                  ChoiceChip(
                    label: Text(category),
                    selected: selectedCategory == category,
                    onSelected: disabled
                        ? null
                        : (_) {
                            onCategoryChanged(category);
                          },
                  ),
              ],
            ),
            const SizedBox(height: 14),
            Text(
              'Safety',
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final safety in const ['All', 'Safe', 'Heavy'])
                  ChoiceChip(
                    label: Text(safety),
                    selected: selectedSafety == safety,
                    onSelected: disabled
                        ? null
                        : (_) {
                            onSafetyChanged(safety);
                          },
                  ),
              ],
            ),
          ],
        ),
      ),
    );
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
            final compact = constraints.maxWidth < 620;

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
                  const _SectionTitle(
                    icon: Icons.event,
                    title: 'Season Control',
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
  final bool requiresConfirmation;
  final int? estimatedTimeoutMinutes;
  final VoidCallback onRun;

  const _CommandCard({
    required this.item,
    required this.isRunning,
    required this.disabled,
    required this.requiresConfirmation,
    required this.estimatedTimeoutMinutes,
    required this.onRun,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final stepCount = item.steps.length;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            LayoutBuilder(
              builder: (context, constraints) {
                final compact = constraints.maxWidth < 620;

                final title = Row(
                  children: [
                    Icon(
                      requiresConfirmation ? Icons.warning_amber_rounded : Icons.admin_panel_settings_outlined,
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        item.label,
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ],
                );

                final chips = Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    Chip(label: Text(item.apiSafeLevel.toUpperCase())),
                    Chip(label: Text(item.category)),
                    Chip(label: Text('$stepCount steps')),
                    if (estimatedTimeoutMinutes != null)
                      Chip(label: Text('${estimatedTimeoutMinutes}m max')),
                    if (requiresConfirmation)
                      const Chip(
                        avatar: Icon(Icons.priority_high, size: 18),
                        label: Text('CONFIRM'),
                      ),
                  ],
                );

                if (compact) {
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      title,
                      const SizedBox(height: 10),
                      chips,
                    ],
                  );
                }

                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: title),
                    const SizedBox(width: 12),
                    Flexible(child: chips),
                  ],
                );
              },
            ),
            const SizedBox(height: 8),
            Text(item.description),
            const SizedBox(height: 12),
            ExpansionTile(
              tilePadding: EdgeInsets.zero,
              childrenPadding: EdgeInsets.zero,
              title: const Text('View CLI steps'),
              children: [
                for (final step in item.steps)
                  Container(
                    width: double.infinity,
                    margin: const EdgeInsets.only(bottom: 8),
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      border: Border.all(
                        color: Theme.of(context).dividerColor,
                      ),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: SelectableText(
                      step,
                      style: theme.textTheme.bodySmall?.copyWith(
                        fontFamily: 'monospace',
                      ),
                    ),
                  ),
              ],
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
                    : Icon(
                        requiresConfirmation ? Icons.warning_amber_rounded : Icons.play_arrow,
                      ),
                label: Text(
                  isRunning
                      ? 'Running...'
                      : requiresConfirmation
                          ? 'Review and Run'
                          : 'Run',
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _HistoryPanel extends StatelessWidget {
  final List<_CommandHistoryItem> history;
  final VoidCallback onClear;

  const _HistoryPanel({
    required this.history,
    required this.onClear,
  });

  @override
  Widget build(BuildContext context) {
    final visible = history.take(8).toList();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Expanded(
                  child: _SectionTitle(
                    icon: Icons.history,
                    title: 'Execution History',
                  ),
                ),
                TextButton.icon(
                  onPressed: onClear,
                  icon: const Icon(Icons.clear),
                  label: const Text('Clear'),
                ),
              ],
            ),
            const SizedBox(height: 8),
            for (final item in visible) ...[
              _HistoryRow(item: item),
              if (item != visible.last) const Divider(),
            ],
          ],
        ),
      ),
    );
  }
}

class _HistoryRow extends StatelessWidget {
  final _CommandHistoryItem item;

  const _HistoryRow({
    required this.item,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final status = item.success ? 'SUCCESS' : 'FAILED';
    final time = _formatTime(item.startedAt);
    final duration = item.durationSeconds == null ? null : '${item.durationSeconds!.toStringAsFixed(2)} sec';

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            item.success ? Icons.check_circle_outline : Icons.error_outline,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  item.label,
                  style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 3),
                Text('$time • ${item.category} • ${item.safety.toUpperCase()}'),
                if (duration != null) Text('Duration: $duration'),
                if (item.failedStep != null) Text('Failed step: ${item.failedStep}'),
                if (item.error != null)
                  Text(
                    item.error!,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          Chip(label: Text(status)),
        ],
      ),
    );
  }

  String _formatTime(DateTime value) {
    final hour = value.hour.toString().padLeft(2, '0');
    final minute = value.minute.toString().padLeft(2, '0');

    return '$hour:$minute';
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
            _SectionTitle(
              icon: isError ? Icons.error_outline : Icons.receipt_long,
              title: title,
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

class _EmptyCommandsView extends StatelessWidget {
  const _EmptyCommandsView();

  @override
  Widget build(BuildContext context) {
    return const Card(
      child: Padding(
        padding: EdgeInsets.all(20),
        child: Column(
          children: [
            Icon(Icons.search_off, size: 42),
            SizedBox(height: 10),
            Text(
              'No commands match the selected filters.',
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final IconData icon;
  final String title;

  const _SectionTitle({
    required this.icon,
    required this.title,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon),
        const SizedBox(width: 10),
        Expanded(
          child: Text(
            title,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
          ),
        ),
      ],
    );
  }
}

class _DialogBullet extends StatelessWidget {
  final String text;

  const _DialogBullet({
    required this.text,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 7),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('•  '),
          Expanded(child: Text(text)),
        ],
      ),
    );
  }
}

class _CommandHistoryItem {
  final String label;
  final String category;
  final String safety;
  final DateTime startedAt;
  final bool success;
  final double? durationSeconds;
  final int? failedStep;
  final String? error;

  const _CommandHistoryItem({
    required this.label,
    required this.category,
    required this.safety,
    required this.startedAt,
    required this.success,
    required this.durationSeconds,
    required this.failedStep,
    this.error,
  });
}