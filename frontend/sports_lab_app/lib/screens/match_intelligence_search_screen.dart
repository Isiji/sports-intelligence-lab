// lib/screens/match_intelligence_search_screen.dart

import 'package:flutter/material.dart';

import '../models/match_summary.dart';
import '../services/prediction_api_service.dart';
import '../widgets/match_card.dart';
import 'match_intelligence_screen.dart';

class MatchIntelligenceSearchScreen extends StatefulWidget {
  const MatchIntelligenceSearchScreen({super.key});

  @override
  State<MatchIntelligenceSearchScreen> createState() =>
      _MatchIntelligenceSearchScreenState();
}

class _MatchIntelligenceSearchScreenState
    extends State<MatchIntelligenceSearchScreen> {
  final PredictionApiService _api = const PredictionApiService();

  final TextEditingController _teamController = TextEditingController();
  final TextEditingController _leagueController = TextEditingController();

  bool _isLoading = false;
  String? _error;

  List<MatchSummary> _matches = [];

  @override
  void dispose() {
    _teamController.dispose();
    _leagueController.dispose();
    super.dispose();
  }

  Future<void> _search() async {
    if (_isLoading) return;

    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final matches = await _api.searchMatches(
        team: _teamController.text,
        league: _leagueController.text,
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

  void _openMatch(MatchSummary match) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => MatchIntelligenceScreen(matchId: match.matchId),
      ),
    );
  }

  void _clear() {
    _teamController.clear();
    _leagueController.clear();

    setState(() {
      _matches = [];
      _error = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FB),
      appBar: AppBar(
        title: const Text('Match Intelligence Search'),
        backgroundColor: const Color(0xFF0F172A),
        foregroundColor: Colors.white,
      ),
      body: RefreshIndicator(
        onRefresh: _search,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _SearchPanel(
              teamController: _teamController,
              leagueController: _leagueController,
              isLoading: _isLoading,
              onSearch: _search,
              onClear: _clear,
            ),
            const SizedBox(height: 14),
            if (_isLoading) const LinearProgressIndicator(),
            if (_error != null) ...[
              const SizedBox(height: 12),
              _ErrorBox(
                message: _error!,
                onRetry: _search,
              ),
            ],
            const SizedBox(height: 16),
            Text(
              'Matches',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w900,
                  ),
            ),
            const SizedBox(height: 10),
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
        side: BorderSide(
          color: Colors.black.withOpacity(0.06),
        ),
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
                hintText: 'Arsenal, Gor Mahia, Man City...',
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
                hintText: 'Premier League, La Liga...',
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
                    label: const Text('Search'),
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
        border: Border.all(
          color: const Color(0xFFFB7185).withOpacity(0.35),
        ),
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
  const _EmptyState();

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
      child: const Column(
        children: [
          Icon(Icons.manage_search_outlined, size: 44, color: Colors.black38),
          SizedBox(height: 10),
          Text(
            'Search for a team or league to open Match Intelligence.',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.black54),
          ),
        ],
      ),
    );
  }
}