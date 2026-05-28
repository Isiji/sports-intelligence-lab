// lib/screens/prediction_explorer_screen.dart

import 'package:flutter/material.dart';

import '../models/match_summary.dart';
import '../services/prediction_api_service.dart';
import '../widgets/match_card.dart';

class PredictionExplorerScreen extends StatefulWidget {
  const PredictionExplorerScreen({super.key});

  @override
  State<PredictionExplorerScreen> createState() =>
      _PredictionExplorerScreenState();
}

class _PredictionExplorerScreenState extends State<PredictionExplorerScreen> {
  final PredictionApiService _api = const PredictionApiService();

  final TextEditingController _teamController = TextEditingController();
  final TextEditingController _leagueController = TextEditingController();

  bool _isLoading = false;
  bool _predictedOnly = false;

  String? _error;
  DateTime _selectedDate = DateTime.now();

  List<MatchSummary> _matches = [];

  @override
  void initState() {
    super.initState();
    _loadSelectedDate();
  }

  @override
  void dispose() {
    _teamController.dispose();
    _leagueController.dispose();
    super.dispose();
  }

  String get _selectedDateLabel {
    final y = _selectedDate.year.toString();
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

    await _loadSelectedDate();
  }

  Future<void> _loadSelectedDate() async {
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
      var matches = await _api.searchMatches(
        team: _teamController.text,
        league: _leagueController.text,
        dateFrom: start,
        dateTo: end,
        limit: 200,
      );

      if (_predictedOnly) {
        matches = matches.where((m) => m.hasPrediction).toList();
      }

      setState(() {
        _matches = matches;
      });
    } catch (e) {
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

    setState(() {
      _predictedOnly = false;
    });

    _loadSelectedDate();
  }

  void _openMatch(MatchSummary match) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          'Next: open Match Intelligence for match ${match.matchId}',
        ),
      ),
    );

    // Next file we will build:
    // Navigator.push(
    //   context,
    //   MaterialPageRoute(
    //     builder: (_) => MatchIntelligenceScreen(matchId: match.matchId),
    //   ),
    // );
  }

  @override
  Widget build(BuildContext context) {
    final predictedCount = _matches.where((m) => m.hasPrediction).length;
    final oddsCount = _matches.where((m) => m.hasOdds).length;

    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FB),
      body: SafeArea(
        child: Column(
          children: [
            _Header(
              selectedDateLabel: _selectedDateLabel,
              totalMatches: _matches.length,
              predictedCount: predictedCount,
              oddsCount: oddsCount,
              isLoading: _isLoading,
              onPickDate: _pickDate,
              onReload: _loadSelectedDate,
            ),
            Expanded(
              child: RefreshIndicator(
                onRefresh: _loadSelectedDate,
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
                  children: [
                    _SearchPanel(
                      teamController: _teamController,
                      leagueController: _leagueController,
                      selectedDateLabel: _selectedDateLabel,
                      predictedOnly: _predictedOnly,
                      isLoading: _isLoading,
                      onPickDate: _pickDate,
                      onLoad: _loadSelectedDate,
                      onClear: _clearFilters,
                      onModeChanged: (value) {
                        setState(() {
                          _predictedOnly = value;
                        });

                        _loadSelectedDate();
                      },
                    ),
                    const SizedBox(height: 14),
                    if (_isLoading) const LinearProgressIndicator(),
                    if (_error != null) ...[
                      const SizedBox(height: 12),
                      _ErrorBox(
                        message: _error!,
                        onRetry: _loadSelectedDate,
                      ),
                    ],
                    const SizedBox(height: 14),
                    _SectionTitle(
                      title: _predictedOnly
                          ? 'Predictions for $_selectedDateLabel'
                          : 'Fixtures for $_selectedDateLabel',
                      subtitle: _predictedOnly
                          ? 'Showing matches already predicted by the system.'
                          : 'Open any fixture to view saved predictions or analyze manually.',
                    ),
                    const SizedBox(height: 12),
                    if (_matches.isEmpty && !_isLoading && _error == null)
                      _EmptyState(
                        predictedOnly: _predictedOnly,
                        selectedDateLabel: _selectedDateLabel,
                      )
                    else
                      ..._matches.map(
                        (match) => MatchCard(
                          match: match,
                          onTap: () => _openMatch(match),
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
  final String selectedDateLabel;
  final int totalMatches;
  final int predictedCount;
  final int oddsCount;
  final bool isLoading;
  final VoidCallback onPickDate;
  final VoidCallback onReload;

  const _Header({
    required this.selectedDateLabel,
    required this.totalMatches,
    required this.predictedCount,
    required this.oddsCount,
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
              const Icon(Icons.analytics_outlined, color: Colors.white),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  'Prediction Explorer',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w800,
                      ),
                ),
              ),
              IconButton(
                onPressed: isLoading ? null : onReload,
                icon: const Icon(Icons.refresh),
                color: Colors.white,
                tooltip: 'Reload',
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            'Search fixtures, inspect predictions, and run on-demand match analysis.',
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
                  const Icon(
                    Icons.calendar_month,
                    color: Colors.white,
                    size: 20,
                  ),
                  const SizedBox(width: 10),
                  Text(
                    selectedDateLabel,
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const Spacer(),
                  const Icon(
                    Icons.keyboard_arrow_down,
                    color: Colors.white,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: _StatTile(
                  label: 'Matches',
                  value: totalMatches.toString(),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _StatTile(
                  label: 'Predicted',
                  value: predictedCount.toString(),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _StatTile(
                  label: 'With odds',
                  value: oddsCount.toString(),
                ),
              ),
            ],
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
      padding: const EdgeInsets.symmetric(
        horizontal: 12,
        vertical: 12,
      ),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.13),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: Colors.white.withOpacity(0.12),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            value,
            style: const TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w900,
              fontSize: 18,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: TextStyle(
              color: Colors.white.withOpacity(0.75),
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }
}

class _SearchPanel extends StatelessWidget {
  final TextEditingController teamController;
  final TextEditingController leagueController;
  final String selectedDateLabel;
  final bool predictedOnly;
  final bool isLoading;
  final VoidCallback onPickDate;
  final VoidCallback onLoad;
  final VoidCallback onClear;
  final ValueChanged<bool> onModeChanged;

  const _SearchPanel({
    required this.teamController,
    required this.leagueController,
    required this.selectedDateLabel,
    required this.predictedOnly,
    required this.isLoading,
    required this.onPickDate,
    required this.onLoad,
    required this.onClear,
    required this.onModeChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 0,
      color: Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(22),
        side: BorderSide(
          color: Colors.black.withOpacity(0.06),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          children: [
            Row(
              children: [
                Expanded(
                  child: _SearchField(
                    controller: teamController,
                    label: 'Team',
                    hint: 'Arsenal, Gor Mahia...',
                    icon: Icons.shield_outlined,
                    onSubmitted: onLoad,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _SearchField(
                    controller: leagueController,
                    label: 'League',
                    hint: 'Premier League...',
                    icon: Icons.emoji_events_outlined,
                    onSubmitted: onLoad,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: isLoading ? null : onPickDate,
                    icon: const Icon(Icons.calendar_month),
                    label: Text(selectedDateLabel),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: isLoading ? null : onLoad,
                    icon: const Icon(Icons.search),
                    label: const Text('Load'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            SegmentedButton<bool>(
              segments: const [
                ButtonSegment<bool>(
                  value: false,
                  icon: Icon(Icons.sports_soccer),
                  label: Text('Fixtures'),
                ),
                ButtonSegment<bool>(
                  value: true,
                  icon: Icon(Icons.analytics_outlined),
                  label: Text('Predictions'),
                ),
              ],
              selected: {predictedOnly},
              onSelectionChanged: isLoading
                  ? null
                  : (value) {
                      onModeChanged(value.first);
                    },
            ),
            const SizedBox(height: 10),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton.icon(
                onPressed: isLoading ? null : onClear,
                icon: const Icon(Icons.clear),
                label: const Text('Clear filters'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SearchField extends StatelessWidget {
  final TextEditingController controller;
  final String label;
  final String hint;
  final IconData icon;
  final VoidCallback onSubmitted;

  const _SearchField({
    required this.controller,
    required this.label,
    required this.hint,
    required this.icon,
    required this.onSubmitted,
  });

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      textInputAction: TextInputAction.search,
      onSubmitted: (_) => onSubmitted(),
      decoration: InputDecoration(
        labelText: label,
        hintText: hint,
        prefixIcon: Icon(icon),
        filled: true,
        fillColor: const Color(0xFFF8FAFC),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(
            color: Colors.black.withOpacity(0.08),
          ),
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
    return Row(
      children: [
        Container(
          width: 5,
          height: 42,
          decoration: BoxDecoration(
            color: const Color(0xFF2563EB),
            borderRadius: BorderRadius.circular(100),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w900,
                    ),
              ),
              const SizedBox(height: 2),
              Text(
                subtitle,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Colors.black54,
                    ),
              ),
            ],
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
        border: Border.all(
          color: const Color(0xFFFB7185).withOpacity(0.35),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(
            Icons.error_outline,
            color: Color(0xFFE11D48),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(
                color: Color(0xFF9F1239),
              ),
            ),
          ),
          TextButton(
            onPressed: onRetry,
            child: const Text('Retry'),
          ),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  final bool predictedOnly;
  final String selectedDateLabel;

  const _EmptyState({
    required this.predictedOnly,
    required this.selectedDateLabel,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(
          color: Colors.black.withOpacity(0.06),
        ),
      ),
      child: Column(
        children: [
          Icon(
            predictedOnly
                ? Icons.analytics_outlined
                : Icons.sports_soccer_outlined,
            size: 46,
            color: Colors.black38,
          ),
          const SizedBox(height: 12),
          Text(
            predictedOnly
                ? 'No predictions found for $selectedDateLabel'
                : 'No fixtures found for $selectedDateLabel',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w800,
                ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 6),
          Text(
            predictedOnly
                ? 'Switch to Fixtures mode, open a match, then run analysis manually.'
                : 'Try another date, team name, or league filter.',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Colors.black54,
                ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}