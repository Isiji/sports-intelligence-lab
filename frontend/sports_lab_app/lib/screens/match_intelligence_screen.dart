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
      final data = await _api.analyzeMatch(
        matchId: widget.matchId,
        market: _selectedMarket,
      );

      if (!mounted) return;

      setState(() {
        _data = data;
      });

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Analysis completed'),
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
                isAnalyzing: _isAnalyzing,
                onMarketChanged: (value) {
                  if (value == null) return;
                  setState(() {
                    _selectedMarket = value;
                  });
                },
                onAnalyze: _analyze,
              ),
              const SizedBox(height: 16),
              if (analysis != null) ...[
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
  final bool isAnalyzing;
  final ValueChanged<String?> onMarketChanged;
  final VoidCallback onAnalyze;

  const _AnalyzePanel({
    required this.markets,
    required this.selectedMarket,
    required this.isAnalyzing,
    required this.onMarketChanged,
    required this.onAnalyze,
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
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Run Market Analysis',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w900,
                  ),
            ),
            const SizedBox(height: 10),
            DropdownButtonFormField<String>(
              value: selectedMarket,
              items: markets
                  .map(
                    (market) => DropdownMenuItem<String>(
                      value: market,
                      child: Text(market),
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
                    : const Icon(Icons.auto_graph),
                label: Text(isAnalyzing ? 'Analyzing...' : 'Analyze'),
              ),
            ),
          ],
        ),
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
                  pick.market,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ),
              _Badge(text: pick.label),
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
            value,
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
              value,
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
            'Choose a market and run analysis.',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.black54),
          ),
        ],
      ),
    );
  }
}