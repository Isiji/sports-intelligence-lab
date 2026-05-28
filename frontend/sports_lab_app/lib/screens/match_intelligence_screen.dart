// lib/screens/match_intelligence_screen.dart

import 'package:flutter/material.dart';

import '../models/match_intelligence.dart';
import '../services/prediction_api_service.dart';

class MatchIntelligenceScreen extends StatefulWidget {
  final int matchId;

  const MatchIntelligenceScreen({
    super.key,
    required this.matchId,
  });

  @override
  State<MatchIntelligenceScreen> createState() =>
      _MatchIntelligenceScreenState();
}

class _MatchIntelligenceScreenState extends State<MatchIntelligenceScreen> {
  final PredictionApiService _api = const PredictionApiService();

  bool _isLoading = true;
  bool _isAnalyzing = false;
  bool _jackpotMode = false;

  String? _error;
  String _selectedMarket = 'home_win';

  MatchIntelligence? _data;

  final List<String> _markets = const [
    'home_win',
    'draw',
    'away_win',
    'over_1_5_goals',
    'over_2_5_goals',
    'under_2_5_goals',
    'btts_yes',
    'btts_no',
    'double_chance_1x',
    'double_chance_x2',
    'double_chance_12',
  ];

  @override
  void initState() {
    super.initState();
    _loadMatch();
  }

  Future<void> _loadMatch() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final data = await _api.getMatchIntelligence(widget.matchId);

      if (!mounted) return;

      setState(() {
        _data = data;
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

  Future<void> _analyze() async {
    setState(() {
      _isAnalyzing = true;
      _error = null;
    });

    try {
      final MatchIntelligence data;

      if (_jackpotMode) {
        data = await _api.analyzeMatch1x2(
          matchId: widget.matchId,
        );
      } else {
        data = await _api.analyzeMatch(
          matchId: widget.matchId,
          market: _selectedMarket,
        );
      }

      if (!mounted) return;

      setState(() {
        _data = data;
      });

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            _jackpotMode
                ? 'Jackpot 1X2 analysis completed'
                : 'Market analysis completed',
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;

      setState(() {
        _error = e.toString();
      });
    } finally {
      if (!mounted) return;

      setState(() {
        _isAnalyzing = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final data = _data;
    final savedPredictions = data?.savedPredictions ?? [];
    final analysis = data?.analysis;
    final jackpot = data == null ? null : Jackpot1x2Result.fromRawOrNull(data.raw);
    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FB),
      appBar: AppBar(
        title: const Text('Match Intelligence'),
        backgroundColor: const Color(0xFF0F172A),
        foregroundColor: Colors.white,
      ),
      body: RefreshIndicator(
        onRefresh: _loadMatch,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (_isLoading) const LinearProgressIndicator(),
            if (_error != null) ...[
              const SizedBox(height: 12),
              _ErrorBox(
                message: _error!,
                onRetry: _loadMatch,
              ),
            ],
            if (data != null) ...[
              _MatchHeader(data: data),
              const SizedBox(height: 14),
              _AnalyzePanel(
                markets: _markets,
                selectedMarket: _selectedMarket,
                jackpotMode: _jackpotMode,
                isAnalyzing: _isAnalyzing,
                onJackpotModeChanged: (value) {
                  setState(() {
                    _jackpotMode = value;
                  });
                },
                onMarketChanged: (value) {
                  if (value == null) return;
                  setState(() {
                    _selectedMarket = value;
                  });
                },
                onAnalyze: _analyze,
              ),
              const SizedBox(height: 16),
              if (jackpot != null) ...[
                _SectionTitle(
                  title: 'Jackpot 1X2 Intelligence',
                  subtitle:
                      'Home, draw and away probabilities analyzed together.',
                ),
                const SizedBox(height: 10),
                _JackpotResultCard(result: jackpot),
                const SizedBox(height: 16),
              ],
              if (analysis != null && jackpot == null) ...[
                _SectionTitle(
                  title: 'Latest Intelligence',
                  subtitle: 'Most recent saved or on-demand prediction result.',
                ),
                const SizedBox(height: 10),
                _PredictionCard(
                  pick: analysis,
                  highlighted: true,
                ),
                const SizedBox(height: 16),
              ],
              _SectionTitle(
                title: 'Saved Predictions',
                subtitle: savedPredictions.isEmpty
                    ? 'No saved predictions found for this match yet.'
                    : 'Predictions already created by your backend.',
              ),
              const SizedBox(height: 10),
              if (savedPredictions.isEmpty)
                const _EmptyPredictions()
              else
                ...savedPredictions.map(
                  (pick) => _PredictionCard(pick: pick),
                ),
            ],
            if (!_isLoading && data == null && _error == null)
              const _EmptyPredictions(),
          ],
        ),
      ),
    );
  }
}

class Jackpot1x2Result {
  final Map<String, dynamic> raw;

  const Jackpot1x2Result({
    required this.raw,
  });

  factory Jackpot1x2Result.fromRaw(Map<String, dynamic> payload) {
    final source = _firstMap([
      payload['jackpot_1x2'],
      payload['jackpot_analysis'],
      payload['jackpot'],
      payload['analysis_1x2'],
      payload['analysis'],
      payload['temporary_analysis'],
      payload,
    ]);

    return Jackpot1x2Result(raw: source);
  }

  static bool existsIn(Map<String, dynamic> payload) {
    final source = _firstMap([
      payload['jackpot_1x2'],
      payload['jackpot_analysis'],
      payload['jackpot'],
      payload['analysis_1x2'],
      payload['analysis'],
      payload['temporary_analysis'],
      payload,
    ]);

    return source.containsKey('home_win_probability') ||
        source.containsKey('draw_probability') ||
        source.containsKey('away_win_probability') ||
        source.containsKey('recommended_pick') ||
        source.containsKey('recommended_label') ||
        source.containsKey('best_double_chance') ||
        source.containsKey('recommended_safe_pick');
  }

  static Jackpot1x2Result? fromRawOrNull(Map<String, dynamic> payload) {
    if (!existsIn(payload)) return null;
    return Jackpot1x2Result.fromRaw(payload);
  }

  double? get homeWinProbability => _doubleValue([
        raw['home_win_probability'],
        raw['home_probability'],
        raw['home_win_prob'],
        raw['probabilities'] is Map
            ? (raw['probabilities'] as Map)['home_win']
            : null,
        raw['probabilities'] is Map ? (raw['probabilities'] as Map)['home'] : null,
      ]);

  double? get drawProbability => _doubleValue([
        raw['draw_probability'],
        raw['draw_prob'],
        raw['probabilities'] is Map ? (raw['probabilities'] as Map)['draw'] : null,
      ]);

  double? get awayWinProbability => _doubleValue([
        raw['away_win_probability'],
        raw['away_probability'],
        raw['away_win_prob'],
        raw['probabilities'] is Map
            ? (raw['probabilities'] as Map)['away_win']
            : null,
        raw['probabilities'] is Map ? (raw['probabilities'] as Map)['away'] : null,
      ]);

  String get recommendedPick => _stringValue([
        raw['recommended_pick'],
        raw['pick'],
        raw['market'],
      ]);

  String get recommendedLabel => _stringValue([
        raw['recommended_label'],
        raw['label'],
        raw['predicted_label'],
        raw['selection'],
      ]);

  double? get confidence => _doubleValue([
        raw['confidence'],
        raw['recommended_confidence'],
      ]);

  String get confidenceBand => _stringValue([
        raw['confidence_band'],
        raw['band'],
      ]);

  String get riskLevel => _stringValue([
        raw['risk_level'],
        raw['risk'],
      ]);

  String get verdict => _stringValue([
        raw['verdict'],
        raw['decision'],
      ]);

  String get reasoning => _stringValue([
        raw['reasoning'],
        raw['explanation'],
      ]);

  String get bestDoubleChance => _stringValue([
        raw['best_double_chance'],
        raw['double_chance'],
      ]);

  String get recommendedSafePick => _stringValue([
        raw['recommended_safe_pick'],
        raw['safe_pick'],
      ]);

  List<dynamic> get alternatives {
    final value = raw['alternatives'];

    if (value is List) return value;

    final nested = raw['market_alternatives'];
    if (nested is List) return nested;

    return const [];
  }
}

class _MatchHeader extends StatelessWidget {
  final MatchIntelligence data;

  const _MatchHeader({
    required this.data,
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
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(26),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            data.league,
            style: TextStyle(
              color: Colors.white.withOpacity(0.78),
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            '${data.homeTeam} vs ${data.awayTeam}',
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              const Icon(
                Icons.schedule,
                color: Colors.white70,
                size: 18,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  data.kickoff,
                  style: const TextStyle(
                    color: Colors.white70,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _AnalyzePanel extends StatelessWidget {
  final List<String> markets;
  final String selectedMarket;
  final bool jackpotMode;
  final bool isAnalyzing;
  final ValueChanged<bool> onJackpotModeChanged;
  final ValueChanged<String?> onMarketChanged;
  final VoidCallback onAnalyze;

  const _AnalyzePanel({
    required this.markets,
    required this.selectedMarket,
    required this.jackpotMode,
    required this.isAnalyzing,
    required this.onJackpotModeChanged,
    required this.onMarketChanged,
    required this.onAnalyze,
  });

  @override
  Widget build(BuildContext context) {
    final title = jackpotMode ? 'Run Jackpot 1X2 Analysis' : 'Run Market Analysis';
    final buttonText = jackpotMode ? 'Analyze 1X2' : 'Analyze Market';

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
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w900,
                  ),
            ),
            const SizedBox(height: 10),
            _ModeToggle(
              jackpotMode: jackpotMode,
              isDisabled: isAnalyzing,
              onChanged: onJackpotModeChanged,
            ),
            const SizedBox(height: 12),
            if (!jackpotMode) ...[
              DropdownButtonFormField<String>(
                value: selectedMarket,
                items: markets
                    .map(
                      (market) => DropdownMenuItem<String>(
                        value: market,
                        child: Text(_marketLabel(market)),
                      ),
                    )
                    .toList(),
                onChanged: isAnalyzing ? null : onMarketChanged,
                decoration: InputDecoration(
                  labelText: 'Market',
                  prefixIcon: const Icon(Icons.tune),
                  filled: true,
                  fillColor: const Color(0xFFF8FAFC),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
              ),
              const SizedBox(height: 12),
            ] else ...[
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFFF8FAFC),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                    color: Colors.black.withOpacity(0.06),
                  ),
                ),
                child: const Row(
                  children: [
                    Icon(
                      Icons.casino_outlined,
                      color: Color(0xFF2563EB),
                    ),
                    SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'Jackpot mode runs Home Win, Draw and Away Win together, then normalizes the probabilities.',
                        style: TextStyle(
                          color: Colors.black87,
                          height: 1.35,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),
            ],
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: isAnalyzing ? null : onAnalyze,
                icon: isAnalyzing
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Icon(jackpotMode ? Icons.casino_outlined : Icons.auto_graph),
                label: Text(isAnalyzing ? 'Analyzing...' : buttonText),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ModeToggle extends StatelessWidget {
  final bool jackpotMode;
  final bool isDisabled;
  final ValueChanged<bool> onChanged;

  const _ModeToggle({
    required this.jackpotMode,
    required this.isDisabled,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(6),
      decoration: BoxDecoration(
        color: const Color(0xFFF1F5F9),
        borderRadius: BorderRadius.circular(18),
      ),
      child: Row(
        children: [
          Expanded(
            child: _ModeButton(
              title: 'Normal',
              subtitle: 'Any market',
              icon: Icons.auto_graph,
              selected: !jackpotMode,
              disabled: isDisabled,
              onTap: () => onChanged(false),
            ),
          ),
          const SizedBox(width: 6),
          Expanded(
            child: _ModeButton(
              title: 'Jackpot',
              subtitle: '1X2 only',
              icon: Icons.casino_outlined,
              selected: jackpotMode,
              disabled: isDisabled,
              onTap: () => onChanged(true),
            ),
          ),
        ],
      ),
    );
  }
}

class _ModeButton extends StatelessWidget {
  final String title;
  final String subtitle;
  final IconData icon;
  final bool selected;
  final bool disabled;
  final VoidCallback onTap;

  const _ModeButton({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.selected,
    required this.disabled,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final color = selected ? const Color(0xFF2563EB) : Colors.black54;

    return InkWell(
      borderRadius: BorderRadius.circular(14),
      onTap: disabled ? null : onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
        decoration: BoxDecoration(
          color: selected ? Colors.white : Colors.transparent,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: selected
                ? const Color(0xFF2563EB).withOpacity(0.25)
                : Colors.transparent,
          ),
        ),
        child: Row(
          children: [
            Icon(icon, color: color, size: 20),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: TextStyle(
                      color: color,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  Text(
                    subtitle,
                    style: TextStyle(
                      color: selected ? Colors.black54 : Colors.black38,
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _JackpotResultCard extends StatelessWidget {
  final Jackpot1x2Result result;

  const _JackpotResultCard({
    required this.result,
  });

  @override
  Widget build(BuildContext context) {
    final confidence = result.confidence;
    final confidenceText =
        confidence == null ? '—' : '${(confidence * 100).toStringAsFixed(1)}%';

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(
          color: Colors.black.withOpacity(0.06),
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.035),
            blurRadius: 20,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _RiskBanner(
            verdict: result.verdict,
            riskLevel: result.riskLevel,
          ),
          const SizedBox(height: 14),
          _RecommendedPickCard(
            recommendedPick: result.recommendedPick,
            recommendedLabel: result.recommendedLabel,
            confidenceText: confidenceText,
            confidenceBand: result.confidenceBand,
          ),
          const SizedBox(height: 14),
          _ProbabilityBars(
            homeWinProbability: result.homeWinProbability,
            drawProbability: result.drawProbability,
            awayWinProbability: result.awayWinProbability,
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: _MiniInsightCard(
                  icon: Icons.security_outlined,
                  label: 'Safe Pick',
                  value: result.recommendedSafePick,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _MiniInsightCard(
                  icon: Icons.call_split_outlined,
                  label: 'Best Double Chance',
                  value: result.bestDoubleChance,
                ),
              ),
            ],
          ),
          if (result.reasoning != '—') ...[
            const SizedBox(height: 14),
            _ReasoningChips(reasoning: result.reasoning),
          ],
          if (result.alternatives.isNotEmpty) ...[
            const SizedBox(height: 14),
            _AlternativesList(alternatives: result.alternatives),
          ],
        ],
      ),
    );
  }
}

class _RiskBanner extends StatelessWidget {
  final String verdict;
  final String riskLevel;

  const _RiskBanner({
    required this.verdict,
    required this.riskLevel,
  });

  @override
  Widget build(BuildContext context) {
    final cleanRisk = riskLevel == '—' ? 'Unknown risk' : riskLevel;
    final cleanVerdict = verdict == '—' ? 'Review before using' : verdict;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(
        color: _riskBackground(cleanRisk),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: _riskColor(cleanRisk).withOpacity(0.22),
        ),
      ),
      child: Row(
        children: [
          Icon(
            Icons.shield_outlined,
            color: _riskColor(cleanRisk),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              cleanVerdict,
              style: TextStyle(
                color: _riskColor(cleanRisk),
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
          const SizedBox(width: 8),
          _Pill(
            text: cleanRisk,
            background: Colors.white.withOpacity(0.7),
            foreground: _riskColor(cleanRisk),
          ),
        ],
      ),
    );
  }

  Color _riskColor(String value) {
    final lower = value.toLowerCase();

    if (lower.contains('low') || lower.contains('safe')) {
      return const Color(0xFF166534);
    }

    if (lower.contains('high') ||
        lower.contains('danger') ||
        lower.contains('avoid') ||
        lower.contains('risky')) {
      return const Color(0xFF9F1239);
    }

    return const Color(0xFF92400E);
  }

  Color _riskBackground(String value) {
    final lower = value.toLowerCase();

    if (lower.contains('low') || lower.contains('safe')) {
      return const Color(0xFFECFDF5);
    }

    if (lower.contains('high') ||
        lower.contains('danger') ||
        lower.contains('avoid') ||
        lower.contains('risky')) {
      return const Color(0xFFFFF1F2);
    }

    return const Color(0xFFFFFBEB);
  }
}

class _RecommendedPickCard extends StatelessWidget {
  final String recommendedPick;
  final String recommendedLabel;
  final String confidenceText;
  final String confidenceBand;

  const _RecommendedPickCard({
    required this.recommendedPick,
    required this.recommendedLabel,
    required this.confidenceText,
    required this.confidenceBand,
  });

  @override
  Widget build(BuildContext context) {
    final pick = recommendedPick == '—' ? 'Recommended Pick' : recommendedPick;
    final label = recommendedLabel == '—' ? 'No label' : recommendedLabel;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [
            Color(0xFFEFF6FF),
            Color(0xFFF8FAFC),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: const Color(0xFF2563EB).withOpacity(0.18),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.workspace_premium_outlined, color: Color(0xFF2563EB)),
              SizedBox(width: 8),
              Text(
                'Recommended Pick',
                style: TextStyle(
                  color: Color(0xFF1E3A8A),
                  fontWeight: FontWeight.w900,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            _marketLabel(pick),
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.w900,
                  color: const Color(0xFF0F172A),
                ),
          ),
          const SizedBox(height: 4),
          Text(
            _marketLabel(label),
            style: const TextStyle(
              color: Colors.black54,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _Metric(
                  label: 'Confidence',
                  value: confidenceText,
                ),
              ),
              Expanded(
                child: _Metric(
                  label: 'Band',
                  value: confidenceBand,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ProbabilityBars extends StatelessWidget {
  final double? homeWinProbability;
  final double? drawProbability;
  final double? awayWinProbability;

  const _ProbabilityBars({
    required this.homeWinProbability,
    required this.drawProbability,
    required this.awayWinProbability,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _ProbabilityBar(
          label: 'Home Win',
          value: homeWinProbability,
          icon: Icons.home_outlined,
        ),
        const SizedBox(height: 10),
        _ProbabilityBar(
          label: 'Draw',
          value: drawProbability,
          icon: Icons.balance_outlined,
        ),
        const SizedBox(height: 10),
        _ProbabilityBar(
          label: 'Away Win',
          value: awayWinProbability,
          icon: Icons.flight_takeoff_outlined,
        ),
      ],
    );
  }
}

class _ProbabilityBar extends StatelessWidget {
  final String label;
  final double? value;
  final IconData icon;

  const _ProbabilityBar({
    required this.label,
    required this.value,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    final normalized = _normalizeProbability(value);
    final percentageText =
        value == null ? '—' : '${(normalized * 100).toStringAsFixed(1)}%';

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Icon(
                icon,
                size: 18,
                color: const Color(0xFF2563EB),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  label,
                  style: const TextStyle(
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              Text(
                percentageText,
                style: const TextStyle(
                  fontWeight: FontWeight.w900,
                  color: Color(0xFF0F172A),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              value: normalized,
              minHeight: 9,
              backgroundColor: Colors.black.withOpacity(0.06),
            ),
          ),
        ],
      ),
    );
  }
}

class _MiniInsightCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;

  const _MiniInsightCard({
    required this.icon,
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    final cleanValue = value == '—' ? 'Not available' : _marketLabel(value);

    return Container(
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: Colors.black.withOpacity(0.05),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            icon,
            color: const Color(0xFF2563EB),
          ),
          const SizedBox(height: 10),
          Text(
            cleanValue,
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
      ),
    );
  }
}

class _ReasoningChips extends StatelessWidget {
  final String reasoning;

  const _ReasoningChips({
    required this.reasoning,
  });

  @override
  Widget build(BuildContext context) {
    final chips = reasoning
        .split(RegExp(r'[.;\n]'))
        .map((item) => item.trim())
        .where((item) => item.isNotEmpty)
        .take(8)
        .toList();

    if (chips.isEmpty) {
      return const SizedBox.shrink();
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Reasoning',
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                fontWeight: FontWeight.w900,
                color: Colors.black54,
              ),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: chips
              .map(
                (chip) => _Pill(
                  text: chip,
                  background: const Color(0xFFEFF6FF),
                  foreground: const Color(0xFF1E3A8A),
                ),
              )
              .toList(),
        ),
      ],
    );
  }
}

class _AlternativesList extends StatelessWidget {
  final List<dynamic> alternatives;

  const _AlternativesList({
    required this.alternatives,
  });

  @override
  Widget build(BuildContext context) {
    final items = alternatives.take(5).toList();

    if (items.isEmpty) {
      return const SizedBox.shrink();
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Alternatives',
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                fontWeight: FontWeight.w900,
                color: Colors.black54,
              ),
        ),
        const SizedBox(height: 8),
        ...items.map((item) => _AlternativeTile(item: item)),
      ],
    );
  }
}

class _AlternativeTile extends StatelessWidget {
  final dynamic item;

  const _AlternativeTile({
    required this.item,
  });

  @override
  Widget build(BuildContext context) {
    final map = item is Map ? item as Map : const {};
    final market = _stringValue([
      map['market'],
      map['pick'],
      map['recommended_pick'],
      map['label'],
      item is String ? item : null,
    ]);

    final label = _stringValue([
      map['label'],
      map['selection'],
      map['recommended_label'],
    ]);

    final confidence = _doubleValue([
      map['confidence'],
      map['probability'],
      map['score'],
    ]);

    final confidenceText =
        confidence == null ? null : '${(_normalizeProbability(confidence) * 100).toStringAsFixed(1)}%';

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(11),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(15),
        border: Border.all(
          color: Colors.black.withOpacity(0.05),
        ),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.alt_route_outlined,
            color: Color(0xFF2563EB),
            size: 18,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              label == '—' ? _marketLabel(market) : '${_marketLabel(market)} · ${_marketLabel(label)}',
              style: const TextStyle(
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          if (confidenceText != null)
            Text(
              confidenceText,
              style: const TextStyle(
                fontWeight: FontWeight.w900,
                color: Color(0xFF0F172A),
              ),
            ),
        ],
      ),
    );
  }
}

class _PredictionCard extends StatelessWidget {
  final PredictionPick pick;
  final bool highlighted;

  const _PredictionCard({
    required this.pick,
    this.highlighted = false,
  });

  @override
  Widget build(BuildContext context) {
    final confidence = pick.confidence == null
        ? '—'
        : '${(pick.confidence! * 100).toStringAsFixed(1)}%';

    final odds = pick.odds == null ? '—' : pick.odds!.toStringAsFixed(2);
    final value =
        pick.valueScore == null ? '—' : pick.valueScore!.toStringAsFixed(3);

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: highlighted ? const Color(0xFFEFF6FF) : Colors.white,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(
          color: highlighted
              ? const Color(0xFF2563EB).withOpacity(0.25)
              : Colors.black.withOpacity(0.06),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.analytics_outlined, color: Color(0xFF2563EB)),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  _marketLabel(pick.market),
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ),
              _Badge(text: _marketLabel(pick.label)),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(child: _Metric(label: 'Confidence', value: confidence)),
              Expanded(child: _Metric(label: 'Odds', value: odds)),
              Expanded(child: _Metric(label: 'Value', value: value)),
            ],
          ),
          const SizedBox(height: 14),
          _InfoRow(
            label: 'Execution market',
            value: pick.executionMarket,
          ),
          _InfoRow(
            label: 'Execution selection',
            value: pick.executionSelection,
          ),
          _InfoRow(
            label: 'Bookmaker',
            value: pick.bookmaker,
          ),
          _InfoRow(
            label: 'Timing risk',
            value: pick.timingRisk,
          ),
          _InfoRow(
            label: 'Local realism',
            value: pick.localRealism,
          ),
          if (pick.reasoning != '—') ...[
            const SizedBox(height: 10),
            Text(
              'Reasoning',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    fontWeight: FontWeight.w800,
                    color: Colors.black54,
                  ),
            ),
            const SizedBox(height: 4),
            Text(
              pick.reasoning,
              style: const TextStyle(
                color: Colors.black87,
                height: 1.35,
              ),
            ),
          ],
        ],
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
    final cleanValue = value == '—' ? value : _marketLabel(value);

    return Container(
      margin: const EdgeInsets.only(right: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            cleanValue,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontWeight: FontWeight.w900,
              fontSize: 16,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: const TextStyle(
              color: Colors.black54,
              fontSize: 11,
            ),
          ),
        ],
      ),
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
    if (value == '—') return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.only(top: 7),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 130,
            child: Text(
              label,
              style: const TextStyle(
                color: Colors.black54,
                fontWeight: FontWeight.w700,
                fontSize: 12,
              ),
            ),
          ),
          Expanded(
            child: Text(
              _marketLabel(value),
              style: const TextStyle(
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Badge extends StatelessWidget {
  final String text;

  const _Badge({
    required this.text,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: 10,
        vertical: 6,
      ),
      decoration: BoxDecoration(
        color: const Color(0xFFDCFCE7),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        text,
        style: const TextStyle(
          color: Color(0xFF166534),
          fontWeight: FontWeight.w900,
          fontSize: 12,
        ),
      ),
    );
  }
}

class _Pill extends StatelessWidget {
  final String text;
  final Color background;
  final Color foreground;

  const _Pill({
    required this.text,
    required this.background,
    required this.foreground,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: 10,
        vertical: 7,
      ),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        _marketLabel(text),
        style: TextStyle(
          color: foreground,
          fontWeight: FontWeight.w900,
          fontSize: 12,
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
      margin: const EdgeInsets.only(bottom: 14),
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
          const Icon(Icons.error_outline, color: Color(0xFFE11D48)),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(color: Color(0xFF9F1239)),
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

class _EmptyPredictions extends StatelessWidget {
  const _EmptyPredictions();

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
          const Icon(
            Icons.analytics_outlined,
            size: 44,
            color: Colors.black38,
          ),
          const SizedBox(height: 10),
          Text(
            'No predictions yet',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Choose normal market analysis or jackpot 1X2 mode.',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.black54),
          ),
        ],
      ),
    );
  }
}

Map<String, dynamic> _firstMap(List<dynamic> values) {
  for (final value in values) {
    if (value is Map<String, dynamic>) {
      return value;
    }

    if (value is Map) {
      return Map<String, dynamic>.from(value);
    }
  }

  return <String, dynamic>{};
}

String _stringValue(List<dynamic> values) {
  for (final value in values) {
    if (value == null) continue;

    final text = value.toString().trim();
    if (text.isNotEmpty && text.toLowerCase() != 'null') {
      return text;
    }
  }

  return '—';
}

double? _doubleValue(List<dynamic> values) {
  for (final value in values) {
    if (value == null) continue;

    if (value is num) {
      return value.toDouble();
    }

    final parsed = double.tryParse(value.toString());
    if (parsed != null) {
      return parsed;
    }
  }

  return null;
}

double _normalizeProbability(double? value) {
  if (value == null) return 0;

  if (value > 1) {
    return (value / 100).clamp(0, 1).toDouble();
  }

  return value.clamp(0, 1).toDouble();
}

String _marketLabel(String value) {
  final clean = value.trim();

  if (clean.isEmpty || clean == '—') {
    return clean.isEmpty ? '—' : clean;
  }

  const labels = {
    'home_win': 'Home Win',
    'draw': 'Draw',
    'away_win': 'Away Win',
    'over_1_5_goals': 'Over 1.5 Goals',
    'over_2_5_goals': 'Over 2.5 Goals',
    'under_2_5_goals': 'Under 2.5 Goals',
    'btts_yes': 'BTTS Yes',
    'btts_no': 'BTTS No',
    'double_chance_1x': 'Double Chance 1X',
    'double_chance_x2': 'Double Chance X2',
    'double_chance_12': 'Double Chance 12',
    '1x': 'Double Chance 1X',
    'x2': 'Double Chance X2',
    '12': 'Double Chance 12',
  };

  final lower = clean.toLowerCase();

  if (labels.containsKey(lower)) {
    return labels[lower]!;
  }

  return clean
      .replaceAll('_', ' ')
      .split(' ')
      .where((part) => part.trim().isNotEmpty)
      .map((part) {
    if (part.length <= 2) return part.toUpperCase();
    return '${part[0].toUpperCase()}${part.substring(1)}';
  }).join(' ');
}