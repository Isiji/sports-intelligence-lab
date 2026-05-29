// lib/screens/jackpot_builder_screen.dart

import 'package:flutter/material.dart';

import '../models/match_summary.dart';
import '../services/prediction_api_service.dart';
import '../widgets/match_card.dart';
import 'match_intelligence_screen.dart';

class JackpotBuilderScreen extends StatefulWidget {
  const JackpotBuilderScreen({super.key});

  @override
  State<JackpotBuilderScreen> createState() => _JackpotBuilderScreenState();
}

class _JackpotBuilderScreenState extends State<JackpotBuilderScreen> {
  final PredictionApiService _api = const PredictionApiService();

  final TextEditingController _teamController = TextEditingController();
  final TextEditingController _leagueController = TextEditingController();

  bool _isLoading = false;
  String? _error;
  DateTime _selectedDate = DateTime.now();

  List<MatchSummary> _matches = [];

  @override
  void initState() {
    super.initState();
    _loadMatches();
  }

  @override
  void dispose() {
    _teamController.dispose();
    _leagueController.dispose();
    super.dispose();
  }

  String get _dateLabel {
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

    await _loadMatches();
  }

  Future<void> _loadMatches() async {
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
      final matches = await _api.searchMatches(
        team: _teamController.text,
        league: _leagueController.text,
        dateFrom: start,
        dateTo: end,
        limit: 100,
      );

      if (!mounted) return;

      setState(() {
        _matches = matches;
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

    _loadMatches();
  }

  void _openMatch(MatchSummary match) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => MatchIntelligenceScreen(matchId: match.matchId),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final predictedCount = _matches.where((m) => m.hasPrediction).length;
    final oddsCount = _matches.where((m) => m.hasOdds).length;

    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FB),
      appBar: AppBar(
        title: const Text('Jackpot / 1X2 Builder'),
        backgroundColor: const Color(0xFF0F172A),
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            onPressed: _isLoading ? null : _loadMatches,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _loadMatches,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _HeaderCard(
              dateLabel: _dateLabel,
              totalMatches: _matches.length,
              predictedCount: predictedCount,
              oddsCount: oddsCount,
              onPickDate: _pickDate,
            ),
            const SizedBox(height: 14),
            _SearchPanel(
              teamController: _teamController,
              leagueController: _leagueController,
              isLoading: _isLoading,
              onSearch: _loadMatches,
              onClear: _clearFilters,
            ),
            const SizedBox(height: 14),
            if (_isLoading) const LinearProgressIndicator(),
            if (_error != null) ...[
              const SizedBox(height: 12),
              _ErrorBox(message: _error!, onRetry: _loadMatches),
            ],
            const SizedBox(height: 16),
            Text(
              'Jackpot Matches',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w900,
                  ),
            ),
            const SizedBox(height: 6),
            const Text(
              'Open a match, switch to Jackpot mode, then run Analyze 1X2.',
              style: TextStyle(
                color: Colors.black54,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 12),
            if (_matches.isEmpty && !_isLoading)
              const _EmptyState()
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
    );
  }
}

class _HeaderCard extends StatelessWidget {
  final String dateLabel;
  final int totalMatches;
  final int predictedCount;
  final int oddsCount;
  final VoidCallback onPickDate;

  const _HeaderCard({
    required this.dateLabel,
    required this.totalMatches,
    required this.predictedCount,
    required this.oddsCount,
    required this.onPickDate,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [
            Color(0xFF0F172A),
            Color(0xFF1E3A8A),
          ],
        ),
        borderRadius: BorderRadius.circular(26),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(
            Icons.confirmation_number_outlined,
            color: Colors.white,
            size: 34,
          ),
          const SizedBox(height: 10),
          Text(
            'Jackpot / 1X2 Builder',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 6),
          Text(
            'Find matches and run Home / Draw / Away intelligence.',
            style: TextStyle(
              color: Colors.white.withOpacity(0.82),
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 14),
          InkWell(
            onTap: onPickDate,
            borderRadius: BorderRadius.circular(16),
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.12),
                borderRadius: BorderRadius.circular(16),
              ),
              child: Row(
                children: [
                  const Icon(Icons.calendar_month, color: Colors.white),
                  const SizedBox(width: 8),
                  Text(
                    dateLabel,
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w900,
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
              _StatBox(label: 'Matches', value: totalMatches.toString()),
              const SizedBox(width: 10),
              _StatBox(label: 'Predicted', value: predictedCount.toString()),
              const SizedBox(width: 10),
              _StatBox(label: 'With Odds', value: oddsCount.toString()),
            ],
          ),
        ],
      ),
    );
  }
}

class _StatBox extends StatelessWidget {
  final String label;
  final String value;

  const _StatBox({
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(11),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.12),
          borderRadius: BorderRadius.circular(15),
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
            Text(
              label,
              style: const TextStyle(
                color: Colors.white70,
                fontSize: 12,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SearchPanel extends StatelessWidget {
  final TextEditingController teamController;
  final TextEditingController leagueController;
  final bool isLoading;
  final VoidCallback onSearch;
  final VoidCallback onClear;

  const _SearchPanel({
    required this.teamController,
    required this.leagueController,
    required this.isLoading,
    required this.onSearch,
    required this.onClear,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 0,
      color: Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(22),
        side: BorderSide(color: Colors.black.withOpacity(0.06)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          children: [
            TextField(
              controller: teamController,
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => onSearch(),
              decoration: InputDecoration(
                labelText: 'Team',
                hintText: 'Arsenal, Gor Mahia...',
                prefixIcon: const Icon(Icons.shield_outlined),
                filled: true,
                fillColor: const Color(0xFFF8FAFC),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: leagueController,
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => onSearch(),
              decoration: InputDecoration(
                labelText: 'League',
                hintText: 'Premier League...',
                prefixIcon: const Icon(Icons.emoji_events_outlined),
                filled: true,
                fillColor: const Color(0xFFF8FAFC),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: FilledButton.icon(
                    onPressed: isLoading ? null : onSearch,
                    icon: const Icon(Icons.search),
                    label: const Text('Load Matches'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: isLoading ? null : onClear,
                    icon: const Icon(Icons.clear),
                    label: const Text('Clear'),
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
        border: Border.all(color: const Color(0xFFFB7185).withOpacity(0.35)),
      ),
      child: Row(
        children: [
          const Icon(Icons.error_outline, color: Color(0xFFE11D48)),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(color: Color(0xFF9F1239)),
            ),
          ),
          TextButton(onPressed: onRetry, child: const Text('Retry')),
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
          Icon(Icons.confirmation_number_outlined, size: 44, color: Colors.black38),
          SizedBox(height: 10),
          Text(
            'No matches found for this date or filters.',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.black54),
          ),
        ],
      ),
    );
  }
}