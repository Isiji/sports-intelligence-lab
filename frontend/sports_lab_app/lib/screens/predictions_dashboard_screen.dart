// lib/screens/predictions_dashboard_screen.dart

import 'package:flutter/material.dart';

import '../models/prediction_dashboard_item.dart';
import '../services/prediction_api_service.dart';
import 'match_intelligence_screen.dart';

class PredictionsDashboardScreen extends StatefulWidget {
  final bool initialExecutionReadyOnly;
  final bool initialKenyanOnly;

  const PredictionsDashboardScreen({
    super.key,
    this.initialExecutionReadyOnly = false,
    this.initialKenyanOnly = false,
  });

  @override
  State<PredictionsDashboardScreen> createState() =>
      _PredictionsDashboardScreenState();
}

class _PredictionsDashboardScreenState
    extends State<PredictionsDashboardScreen> {
  final PredictionApiService _api = const PredictionApiService();

  final TextEditingController _teamController = TextEditingController();
  final TextEditingController _leagueController = TextEditingController();
  final TextEditingController _marketController = TextEditingController();
  final TextEditingController _slateController = TextEditingController();

  bool _isLoading = false;
  bool _executionReadyOnly = false;
  bool _kenyanOnly = false;

  double _minConfidence = 0.0;
  DateTime _selectedDate = DateTime.now();

  String? _error;
  List<PredictionDashboardItem> _items = [];

  @override
  void initState() {
    super.initState();
    _executionReadyOnly = widget.initialExecutionReadyOnly;
    _kenyanOnly = widget.initialKenyanOnly;
    _loadPredictions();
  }

  @override
  void dispose() {
    _teamController.dispose();
    _leagueController.dispose();
    _marketController.dispose();
    _slateController.dispose();
    super.dispose();
  }

  String get _dateLabel {
    final y = _selectedDate.year.toString().padLeft(4, '0');
    final m = _selectedDate.month.toString().padLeft(2, '0');
    final d = _selectedDate.day.toString().padLeft(2, '0');
    return '$y-$m-$d';
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedDate,
      firstDate: DateTime(2020),
      lastDate: DateTime(2035),
    );

    if (picked == null) return;

    setState(() {
      _selectedDate = picked;
    });

    await _loadPredictions();
  }

  Future<void> _loadPredictions() async {
    if (_isLoading) return;

    final start = DateTime(
      _selectedDate.year,
      _selectedDate.month,
      _selectedDate.day,
    );

    final end = start.add(const Duration(days: 1)).subtract(
          const Duration(seconds: 1),
        );

    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final items = await _api.searchPredictionsDashboard(
        team: _teamController.text,
        league: _leagueController.text,
        market: _marketController.text,
        slate: _slateController.text,
        dateFrom: start,
        dateTo: end,
        minConfidence: _minConfidence,
        executionReadyOnly: _executionReadyOnly,
        kenyanOnly: _kenyanOnly,
        limit: 200,
      );

      if (!mounted) return;

      setState(() {
        _items = items;
      });
    } catch (e) {
      if (!mounted) return;

      setState(() {
        _error = e.toString();
      });
    } finally {
      if (!mounted) return;

      setState(() {
        _isLoading = false;
      });
    }
  }

  void _clearFilters() {
    _teamController.clear();
    _leagueController.clear();
    _marketController.clear();
    _slateController.clear();

    setState(() {
      _minConfidence = 0.0;
      _executionReadyOnly = false;
      _kenyanOnly = false;
    });

    _loadPredictions();
  }

  void _openMatch(PredictionDashboardItem item) {
    final matchId = item.matchId;

    if (matchId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('This prediction has no match_id.'),
        ),
      );
      return;
    }

    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => MatchIntelligenceScreen(matchId: matchId),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final executionReadyCount = _items.where((x) => x.executionReady).length;
    final kenyanCount = _items.where((x) => x.isKenyanPick).length;

    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FB),
      body: SafeArea(
        child: Column(
          children: [
            _Header(
              dateLabel: _dateLabel,
              total: _items.length,
              executionReady: executionReadyCount,
              kenyan: kenyanCount,
              isLoading: _isLoading,
              onPickDate: _pickDate,
              onReload: _loadPredictions,
            ),
            Expanded(
              child: RefreshIndicator(
                onRefresh: _loadPredictions,
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
                  children: [
                    _FilterPanel(
                      teamController: _teamController,
                      leagueController: _leagueController,
                      marketController: _marketController,
                      slateController: _slateController,
                      dateLabel: _dateLabel,
                      minConfidence: _minConfidence,
                      executionReadyOnly: _executionReadyOnly,
                      kenyanOnly: _kenyanOnly,
                      isLoading: _isLoading,
                      onPickDate: _pickDate,
                      onSearch: _loadPredictions,
                      onClear: _clearFilters,
                      onMinConfidenceChanged: (value) {
                        setState(() {
                          _minConfidence = value;
                        });
                      },
                      onExecutionReadyChanged: (value) {
                        setState(() {
                          _executionReadyOnly = value;
                        });
                        _loadPredictions();
                      },
                      onKenyanOnlyChanged: (value) {
                        setState(() {
                          _kenyanOnly = value;
                        });
                        _loadPredictions();
                      },
                    ),
                    const SizedBox(height: 14),
                    if (_isLoading) const LinearProgressIndicator(),
                    if (_error != null) ...[
                      const SizedBox(height: 12),
                      _ErrorBox(
                        message: _error!,
                        onRetry: _loadPredictions,
                      ),
                    ],
                    const SizedBox(height: 14),
                    _SectionTitle(
                      title: 'Predictions for $_dateLabel',
                      subtitle:
                          'Open any prediction to inspect Match Intelligence, Execution Intelligence and Market Alternatives.',
                    ),
                    const SizedBox(height: 12),
                    if (_items.isEmpty && !_isLoading && _error == null)
                      const _EmptyState()
                    else
                      ..._items.map(
                        (item) => _PredictionCard(
                          item: item,
                          onOpenMatch: () => _openMatch(item),
                          onOpenExecution: () => _openMatch(item),
                          onOpenAlternatives: () => _openMatch(item),
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  final String dateLabel;
  final int total;
  final int executionReady;
  final int kenyan;
  final bool isLoading;
  final VoidCallback onPickDate;
  final VoidCallback onReload;

  const _Header({
    required this.dateLabel,
    required this.total,
    required this.executionReady,
    required this.kenyan,
    required this.isLoading,
    required this.onPickDate,
    required this.onReload,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(18, 18, 18, 18),
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          colors: [
            Color(0xFF0F172A),
            Color(0xFF1E3A8A),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.vertical(
          bottom: Radius.circular(28),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.dashboard_customize_outlined, color: Colors.white),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  'Predictions Dashboard',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ),
              IconButton(
                onPressed: isLoading ? null : onReload,
                icon: const Icon(Icons.refresh),
                color: Colors.white,
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            'All model picks with confidence, odds, execution readiness and Kenyan suitability.',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Colors.white.withOpacity(0.82),
                ),
          ),
          const SizedBox(height: 16),
          InkWell(
            onTap: isLoading ? null : onPickDate,
            borderRadius: BorderRadius.circular(18),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.12),
                borderRadius: BorderRadius.circular(18),
                border: Border.all(
                  color: Colors.white.withOpacity(0.18),
                ),
              ),
              child: Row(
                children: [
                  const Icon(Icons.calendar_month, color: Colors.white),
                  const SizedBox(width: 10),
                  Text(
                    dateLabel,
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const Spacer(),
                  const Icon(Icons.keyboard_arrow_down, color: Colors.white),
                ],
              ),
            ),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(child: _StatTile(label: 'Predictions', value: '$total')),
              const SizedBox(width: 10),
              Expanded(
                child: _StatTile(label: 'Execution', value: '$executionReady'),
              ),
              const SizedBox(width: 10),
              Expanded(child: _StatTile(label: 'Kenyan', value: '$kenyan')),
            ],
          ),
        ],
      ),
    );
  }
}

class _FilterPanel extends StatelessWidget {
  final TextEditingController teamController;
  final TextEditingController leagueController;
  final TextEditingController marketController;
  final TextEditingController slateController;
  final String dateLabel;
  final double minConfidence;
  final bool executionReadyOnly;
  final bool kenyanOnly;
  final bool isLoading;
  final VoidCallback onPickDate;
  final VoidCallback onSearch;
  final VoidCallback onClear;
  final ValueChanged<double> onMinConfidenceChanged;
  final ValueChanged<bool> onExecutionReadyChanged;
  final ValueChanged<bool> onKenyanOnlyChanged;

  const _FilterPanel({
    required this.teamController,
    required this.leagueController,
    required this.marketController,
    required this.slateController,
    required this.dateLabel,
    required this.minConfidence,
    required this.executionReadyOnly,
    required this.kenyanOnly,
    required this.isLoading,
    required this.onPickDate,
    required this.onSearch,
    required this.onClear,
    required this.onMinConfidenceChanged,
    required this.onExecutionReadyChanged,
    required this.onKenyanOnlyChanged,
  });

  @override
  Widget build(BuildContext context) {
    final confidencePercent = (minConfidence * 100).round();

    return Card(
      elevation: 0,
      color: Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(24),
        side: BorderSide(color: Colors.black.withOpacity(0.06)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          children: [
            Row(
              children: [
                Expanded(
                  child: _Input(
                    controller: teamController,
                    label: 'Team',
                    icon: Icons.sports_soccer,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _Input(
                    controller: leagueController,
                    label: 'League',
                    icon: Icons.emoji_events_outlined,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: _Input(
                    controller: marketController,
                    label: 'Market',
                    icon: Icons.tune,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _Input(
                    controller: slateController,
                    label: 'Slate',
                    icon: Icons.list_alt_outlined,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            InkWell(
              onTap: isLoading ? null : onPickDate,
              borderRadius: BorderRadius.circular(16),
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(13),
                decoration: BoxDecoration(
                  color: const Color(0xFFF8FAFC),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: Colors.black.withOpacity(0.06)),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.calendar_today_outlined),
                    const SizedBox(width: 10),
                    Text(
                      dateLabel,
                      style: const TextStyle(fontWeight: FontWeight.w800),
                    ),
                    const Spacer(),
                    const Icon(Icons.keyboard_arrow_down),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                const Text(
                  'Min confidence',
                  style: TextStyle(fontWeight: FontWeight.w800),
                ),
                const Spacer(),
                Text(
                  '$confidencePercent%',
                  style: const TextStyle(fontWeight: FontWeight.w900),
                ),
              ],
            ),
            Slider(
              value: minConfidence,
              min: 0,
              max: 0.95,
              divisions: 19,
              label: '$confidencePercent%',
              onChanged: isLoading ? null : onMinConfidenceChanged,
              onChangeEnd: (_) => onSearch(),
            ),
            SwitchListTile(
              value: executionReadyOnly,
              onChanged: isLoading ? null : onExecutionReadyChanged,
              title: const Text('Execution ready only'),
              subtitle: const Text('Show picks passing execution readiness.'),
              contentPadding: EdgeInsets.zero,
            ),
            SwitchListTile(
              value: kenyanOnly,
              onChanged: isLoading ? null : onKenyanOnlyChanged,
              title: const Text('Kenyan / local picks only'),
              subtitle: const Text('Show locally suitable bookmaker picks.'),
              contentPadding: EdgeInsets.zero,
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: isLoading ? null : onClear,
                    icon: const Icon(Icons.clear),
                    label: const Text('Clear'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: isLoading ? null : onSearch,
                    icon: const Icon(Icons.search),
                    label: const Text('Search'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _PredictionCard extends StatelessWidget {
  final PredictionDashboardItem item;
  final VoidCallback onOpenMatch;
  final VoidCallback onOpenExecution;
  final VoidCallback onOpenAlternatives;

  const _PredictionCard({
    required this.item,
    required this.onOpenMatch,
    required this.onOpenExecution,
    required this.onOpenAlternatives,
  });

  @override
  Widget build(BuildContext context) {
    final readyColor =
        item.executionReady ? const Color(0xFF166534) : const Color(0xFF92400E);

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: Colors.black.withOpacity(0.06)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                item.executionReady
                    ? Icons.check_circle_outline
                    : Icons.warning_amber_rounded,
                color: readyColor,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  item.league,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Colors.black54,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              if (item.isKenyanPick)
                const _Pill(
                  text: 'Kenyan',
                  color: Color(0xFF166534),
                ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            '${item.homeTeam} vs ${item.awayTeam}',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w900,
                  color: const Color(0xFF0F172A),
                ),
          ),
          const SizedBox(height: 4),
          Text(
            item.kickoff,
            style: const TextStyle(
              color: Colors.black54,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _Metric(
                  label: 'Market',
                  value: _label(item.market),
                ),
              ),
              Expanded(
                child: _Metric(
                  label: 'Pick',
                  value: _label(item.predictedLabel),
                ),
              ),
              Expanded(
                child: _Metric(
                  label: 'Confidence',
                  value: item.confidenceText,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(child: _Metric(label: 'Odds', value: item.oddsText)),
              Expanded(
                child: _Metric(
                  label: 'Execution',
                  value: item.executionScoreText,
                ),
              ),
              Expanded(
                child: _Metric(
                  label: 'Survivability',
                  value: item.survivabilityText,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          _InfoRow(label: 'Execution market', value: _label(item.executionMarket)),
          _InfoRow(
            label: 'Execution selection',
            value: _label(item.executionSelection),
          ),
          _InfoRow(label: 'Bookmaker', value: item.bookmaker),
          _InfoRow(label: 'Locality', value: item.bookmakerLocality),
          _InfoRow(label: 'Slate', value: item.slate),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: onOpenMatch,
                  icon: const Icon(Icons.analytics_outlined),
                  label: const Text('Match'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: onOpenExecution,
                  icon: const Icon(Icons.verified_outlined),
                  label: const Text('Execution'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: FilledButton.icon(
                  onPressed: onOpenAlternatives,
                  icon: const Icon(Icons.compare_arrows_outlined),
                  label: const Text('Markets'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _Input extends StatelessWidget {
  final TextEditingController controller;
  final String label;
  final IconData icon;

  const _Input({
    required this.controller,
    required this.label,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      textInputAction: TextInputAction.search,
      decoration: InputDecoration(
        labelText: label,
        prefixIcon: Icon(icon),
        filled: true,
        fillColor: const Color(0xFFF8FAFC),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
        ),
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  final String label;
  final String value;

  const _Metric({
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    final clean = value == '—' ? 'Unknown' : value;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          clean,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(
            fontWeight: FontWeight.w900,
            color: Color(0xFF0F172A),
          ),
        ),
        const SizedBox(height: 2),
        Text(
          label,
          style: const TextStyle(
            color: Colors.black54,
            fontSize: 12,
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    );
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;

  const _InfoRow({
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    if (value == '—' || value.trim().isEmpty) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.only(bottom: 5),
      child: Row(
        children: [
          SizedBox(
            width: 130,
            child: Text(
              label,
              style: const TextStyle(
                color: Colors.black54,
                fontSize: 12,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(
                color: Colors.black87,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _StatTile extends StatelessWidget {
  final String label;
  final String value;

  const _StatTile({
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.13),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white.withOpacity(0.16)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            value,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 20,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: TextStyle(
              color: Colors.white.withOpacity(0.72),
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class _Pill extends StatelessWidget {
  final String text;
  final Color color;

  const _Pill({
    required this.text,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: color.withOpacity(0.10),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withOpacity(0.25)),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: color,
          fontSize: 12,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final String title;
  final String subtitle;

  const _SectionTitle({
    required this.title,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w900,
              ),
        ),
        const SizedBox(height: 4),
        Text(
          subtitle,
          style: const TextStyle(
            color: Colors.black54,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }
}

class _ErrorBox extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const _ErrorBox({
    required this.message,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF1F2),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFFBE123C).withOpacity(0.20)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Could not load predictions',
            style: TextStyle(
              color: Color(0xFF9F1239),
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            message,
            style: const TextStyle(color: Color(0xFF9F1239)),
          ),
          const SizedBox(height: 10),
          OutlinedButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh),
            label: const Text('Retry'),
          ),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: Colors.black.withOpacity(0.06)),
      ),
      child: const Column(
        children: [
          Icon(
            Icons.inbox_outlined,
            size: 42,
            color: Colors.black45,
          ),
          SizedBox(height: 10),
          Text(
            'No predictions found',
            style: TextStyle(
              fontWeight: FontWeight.w900,
              color: Color(0xFF0F172A),
            ),
          ),
          SizedBox(height: 4),
          Text(
            'Try changing the date, team, market, league or confidence filters.',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.black54),
          ),
        ],
      ),
    );
  }
}

String _label(String value) {
  if (value == '—') return value;

  return value
      .replaceAll('_', ' ')
      .split(' ')
      .where((part) => part.trim().isNotEmpty)
      .map((part) {
    if (part.length <= 2) return part.toUpperCase();
    return '${part[0].toUpperCase()}${part.substring(1)}';
  }).join(' ');
}