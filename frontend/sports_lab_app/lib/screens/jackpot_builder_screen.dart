// lib/screens/jackpot_builder_screen.dart
// Full replacement file

import 'package:flutter/material.dart';

import '../models/match_intelligence.dart';
import '../models/match_summary.dart';
import '../models/slip_pick.dart';
import '../services/prediction_api_service.dart';

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

  final List<MatchSummary> _matches = [];
  final List<SlipPick> _jackpotPicks = [];

  final Map<int, MatchIntelligence> _analysisByMatchId = {};
  final Set<int> _analyzingMatchIds = {};

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
      _analysisByMatchId.clear();
      _analyzingMatchIds.clear();
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
        team: _teamController.text.trim(),
        league: _leagueController.text.trim(),
        dateFrom: start,
        dateTo: end,
        limit: 100,
      );

      if (!mounted) return;

      setState(() {
        _matches
          ..clear()
          ..addAll(matches);
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
    _analysisByMatchId.clear();
    _analyzingMatchIds.clear();
    _loadMatches();
  }

  Future<void> _analyzeJackpot1x2(MatchSummary match) async {
    final matchId = match.matchId;

    if (_analyzingMatchIds.contains(matchId)) return;

    setState(() {
      _analyzingMatchIds.add(matchId);
      _error = null;
    });

    try {
      final analysis = await _api.analyzeMatch1x2(matchId: matchId);

      if (!mounted) return;

      setState(() {
        _analysisByMatchId[matchId] = analysis;
      });
    } catch (e) {
      if (!mounted) return;

      setState(() {
        _error = e.toString();
      });
    } finally {
      if (!mounted) return;

      setState(() {
        _analyzingMatchIds.remove(matchId);
      });
    }
  }

  void _addJackpotPick({
    required MatchSummary summary,
    required MatchIntelligence analysis,
    required Jackpot1x2Result result,
  }) {
    final pick = SlipPick.fromJackpotAnalysis(
      match: analysis,
      result: result,
    );

    final fixedPick = SlipPick(
      matchId: pick.matchId ?? summary.matchId,
      league: pick.league == '—' ? summary.league : pick.league,
      homeTeam: pick.homeTeam == '—' ? summary.homeTeam : pick.homeTeam,
      awayTeam: pick.awayTeam == '—' ? summary.awayTeam : pick.awayTeam,
      kickoff: pick.kickoff == '—' ? (summary.kickoffEat ?? '—') : pick.kickoff,
      market: 'jackpot_1x2',
      selection: pick.selection,
      confidence: pick.confidence,
      odds: pick.odds,
      executionScore: pick.executionScore,
      survivabilityScore: pick.survivabilityScore,
      localRealismScore: pick.localRealismScore,
      bookmaker: pick.bookmaker,
      bookmakerLocality: pick.bookmakerLocality,
      mode: 'jackpot',
    );

    setState(() {
      _jackpotPicks.removeWhere((item) => item.matchId == fixedPick.matchId);
      _jackpotPicks.add(fixedPick);
    });

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          'Added ${fixedPick.selection} - ${fixedPick.jackpotLabel} for ${fixedPick.matchTitle}',
        ),
      ),
    );
  }

  bool _isAlreadyPicked(int matchId) {
    return _jackpotPicks.any((pick) => pick.matchId == matchId);
  }

  @override
  Widget build(BuildContext context) {
    final predictedCount = _matches.where((m) => m.hasPrediction).length;
    final oddsCount = _matches.where((m) => m.hasOdds).length;

    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FB),
      appBar: AppBar(
        title: const Text('Jackpot Builder'),
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
              pickCount: _jackpotPicks.length,
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
              'Analyze each match directly here. Jackpot mode only returns 1, X, or 2.',
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
                (match) {
                  final analysis = _analysisByMatchId[match.matchId];
                  final result = analysis?.jackpot1x2;
                  final isAnalyzing = _analyzingMatchIds.contains(match.matchId);

                  return _JackpotMatchCard(
                    match: match,
                    analysis: analysis,
                    result: result,
                    isAnalyzing: isAnalyzing,
                    isPicked: _isAlreadyPicked(match.matchId),
                    onAnalyze: () => _analyzeJackpot1x2(match),
                    onAddPick: analysis != null && result != null
                        ? () => _addJackpotPick(
                              summary: match,
                              analysis: analysis,
                              result: result,
                            )
                        : null,
                  );
                },
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
  final int pickCount;
  final VoidCallback onPickDate;

  const _HeaderCard({
    required this.dateLabel,
    required this.totalMatches,
    required this.predictedCount,
    required this.oddsCount,
    required this.pickCount,
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
            'Clean jackpot analysis: 1 Home, X Draw, 2 Away only.',
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
              _StatBox(label: 'Odds', value: oddsCount.toString()),
              const SizedBox(width: 10),
              _StatBox(label: 'Picks', value: pickCount.toString()),
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

class _JackpotMatchCard extends StatelessWidget {
  final MatchSummary match;
  final MatchIntelligence? analysis;
  final Jackpot1x2Result? result;
  final bool isAnalyzing;
  final bool isPicked;
  final VoidCallback onAnalyze;
  final VoidCallback? onAddPick;

  const _JackpotMatchCard({
    required this.match,
    required this.analysis,
    required this.result,
    required this.isAnalyzing,
    required this.isPicked,
    required this.onAnalyze,
    required this.onAddPick,
  });

  @override
  Widget build(BuildContext context) {
    final homeProbability = result?.homeWinProbability;
    final drawProbability = result?.drawProbability;
    final awayProbability = result?.awayWinProbability;

    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 14),
      color: Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(22),
        side: BorderSide(color: Colors.black.withOpacity(0.06)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    '${match.homeTeam} vs ${match.awayTeam}',
                    style: const TextStyle(
                      fontWeight: FontWeight.w900,
                      fontSize: 16,
                    ),
                  ),
                ),
                if (isPicked)
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 6,
                    ),
                    decoration: BoxDecoration(
                      color: const Color(0xFFDCFCE7),
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: const Text(
                      'Picked',
                      style: TextStyle(
                        color: Color(0xFF166534),
                        fontWeight: FontWeight.w900,
                        fontSize: 12,
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              '${match.league} • ${match.kickoffEat ?? 'Kickoff unavailable'}',
              style: const TextStyle(
                color: Colors.black54,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                _OutcomeBox(
                  code: '1',
                  label: 'Home',
                  probability: homeProbability,
                  selected: result?.jackpotSelection == '1',
                ),
                const SizedBox(width: 8),
                _OutcomeBox(
                  code: 'X',
                  label: 'Draw',
                  probability: drawProbability,
                  selected: result?.jackpotSelection == 'X',
                ),
                const SizedBox(width: 8),
                _OutcomeBox(
                  code: '2',
                  label: 'Away',
                  probability: awayProbability,
                  selected: result?.jackpotSelection == '2',
                ),
              ],
            ),
            if (result != null) ...[
              const SizedBox(height: 14),
              _ResultPanel(result: result!),
            ],
            const SizedBox(height: 14),
            Row(
              children: [
                Expanded(
                  child: FilledButton.icon(
                    onPressed: isAnalyzing ? null : onAnalyze,
                    icon: isAnalyzing
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.analytics_outlined),
                    label: Text(
                      isAnalyzing ? 'Analyzing...' : 'Analyze 1X2',
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: onAddPick,
                    icon: const Icon(Icons.add_circle_outline),
                    label: const Text('Jackpot Pick'),
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

class _OutcomeBox extends StatelessWidget {
  final String code;
  final String label;
  final double? probability;
  final bool selected;

  const _OutcomeBox({
    required this.code,
    required this.label,
    required this.probability,
    required this.selected,
  });

  @override
  Widget build(BuildContext context) {
    final percent = probability == null
        ? '—'
        : '${(probability! * 100).toStringAsFixed(1)}%';

    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(11),
        decoration: BoxDecoration(
          color: selected ? const Color(0xFFEFF6FF) : const Color(0xFFF8FAFC),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: selected ? const Color(0xFF2563EB) : const Color(0xFFE2E8F0),
            width: selected ? 1.4 : 1,
          ),
        ),
        child: Column(
          children: [
            Text(
              code,
              style: TextStyle(
                fontWeight: FontWeight.w900,
                fontSize: 20,
                color: selected ? const Color(0xFF1D4ED8) : Colors.black87,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              label,
              style: const TextStyle(
                fontWeight: FontWeight.w800,
                color: Colors.black54,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              percent,
              style: const TextStyle(
                fontWeight: FontWeight.w900,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ResultPanel extends StatelessWidget {
  final Jackpot1x2Result result;

  const _ResultPanel({
    required this.result,
  });

  @override
  Widget build(BuildContext context) {
    final confidence = result.confidence == null
        ? '—'
        : '${(result.confidence! * 100).toStringAsFixed(1)}%';

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFFE2E8F0)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoLine(label: 'Pick', value: _pickLabel(result)),
          _InfoLine(label: 'Confidence', value: confidence),
          _InfoLine(label: 'Risk', value: result.riskLevel),
          _InfoLine(label: 'Verdict', value: result.verdict),
          if (result.reasoning.isNotEmpty) ...[
            const SizedBox(height: 8),
            const Text(
              'Reasoning',
              style: TextStyle(
                fontWeight: FontWeight.w900,
                color: Colors.black87,
              ),
            ),
            const SizedBox(height: 4),
            ...result.reasoning.map(
              (reason) => Padding(
                padding: const EdgeInsets.only(bottom: 3),
                child: Text(
                  '• $reason',
                  style: const TextStyle(
                    color: Colors.black87,
                    height: 1.35,
                  ),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  String _pickLabel(Jackpot1x2Result result) {
    if (result.jackpotSelection == '1') return '1 Home';
    if (result.jackpotSelection == 'X') return 'X Draw';
    if (result.jackpotSelection == '2') return '2 Away';
    return result.jackpotSelection;
  }
}

class _InfoLine extends StatelessWidget {
  final String label;
  final String value;

  const _InfoLine({
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    final cleanValue = value.trim().isEmpty ? '—' : value;

    return Padding(
      padding: const EdgeInsets.only(bottom: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 92,
            child: Text(
              label,
              style: const TextStyle(
                color: Colors.black54,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          Expanded(
            child: Text(
              cleanValue,
              style: const TextStyle(
                color: Colors.black87,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
        ],
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
          Icon(
            Icons.confirmation_number_outlined,
            size: 44,
            color: Colors.black38,
          ),
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