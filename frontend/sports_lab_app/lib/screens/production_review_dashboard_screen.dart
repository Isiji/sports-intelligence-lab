// lib/screens/production_review_dashboard_screen.dart

import 'package:flutter/material.dart';

import '../models/production_review.dart';
import '../services/production_review_api_service.dart';
import '../widgets/production_health_cards.dart';
import '../widgets/production_pick_card.dart';

class ProductionReviewDashboardScreen extends StatefulWidget {
  const ProductionReviewDashboardScreen({super.key});

  @override
  State<ProductionReviewDashboardScreen> createState() =>
      _ProductionReviewDashboardScreenState();
}

class _ProductionReviewDashboardScreenState
    extends State<ProductionReviewDashboardScreen> {
  final ProductionReviewApiService _service =
      const ProductionReviewApiService();

  final TextEditingController _marketController = TextEditingController();
  final TextEditingController _leagueController = TextEditingController();

  List<String> _availableSlates = [];
  String? _selectedSlate;

  bool _requireOdds = false;
  bool _loading = true;
  bool _loadingSlates = true;
  String? _error;
  ProductionReview? _review;

  @override
  void initState() {
    super.initState();
    _loadSlatesThenReview();
  }

  @override
  void dispose() {
    _marketController.dispose();
    _leagueController.dispose();
    super.dispose();
  }

  Future<void> _loadSlatesThenReview() async {
    setState(() {
      _loading = true;
      _loadingSlates = true;
      _error = null;
    });

    try {
      final slates = await _service.getAvailableSlates();

      final selected = slates.isNotEmpty ? slates.first : null;

      setState(() {
        _availableSlates = slates;
        _selectedSlate = selected;
        _loadingSlates = false;
      });

      await _loadReview();
    } catch (e) {
      setState(() {
        _error = '$e';
        _loading = false;
        _loadingSlates = false;
      });
    }
  }

  Future<void> _loadReview() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final review = await _service.getProductionReview(
        slate: _selectedSlate,
        market: _marketController.text,
        league: _leagueController.text,
        requireOdds: _requireOdds,
      );

      setState(() {
        _review = review;
        _loading = false;

        if (_selectedSlate == null || _selectedSlate!.trim().isEmpty) {
          _selectedSlate = review.slate;
        }

        if (!_availableSlates.contains(review.slate) &&
            review.slate.trim().isNotEmpty) {
          _availableSlates = [
            review.slate,
            ..._availableSlates,
          ];
        }
      });
    } catch (e) {
      setState(() {
        _error = '$e';
        _loading = false;
      });
    }
  }

  Future<void> _refreshAll() async {
    await _loadSlatesThenReview();
  }

  @override
  Widget build(BuildContext context) {
    final review = _review;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Production Review'),
        actions: [
          IconButton(
            tooltip: 'Refresh slates and review',
            onPressed: _refreshAll,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refreshAll,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _filters(),
            const SizedBox(height: 16),
            if (_loading)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(40),
                  child: CircularProgressIndicator(),
                ),
              )
            else if (_error != null)
              _errorBox(_error!)
            else if (review == null)
              const Text('No production review found.')
            else ...[
              Text(
                'Slate: ${review.slate}',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
              ),
              const SizedBox(height: 16),
              ProductionHealthCards(
                summary: review.summary,
                health: review.productionHealth,
              ),
              const SizedBox(height: 24),
              _recommendationSummary(review),
              const SizedBox(height: 24),
              _sectionTitle('Ranked Picks'),
              const SizedBox(height: 8),
              if (review.rankedPicks.isEmpty)
                const Text('No ranked picks found.')
              else
                ...review.rankedPicks.map(
                  (pick) => ProductionPickCard(pick: pick),
                ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _filters() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          children: [
            DropdownButtonFormField<String>(
              initialValue: _selectedSlate,
              isExpanded: true,
              decoration: InputDecoration(
                labelText: _loadingSlates ? 'Loading slates...' : 'Slate',
                prefixIcon: const Icon(Icons.view_list_outlined),
              ),
              items: _availableSlates
                  .map(
                    (slate) => DropdownMenuItem<String>(
                      value: slate,
                      child: Text(
                        slate,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  )
                  .toList(),
              onChanged: (value) {
                setState(() {
                  _selectedSlate = value;
                });

                _loadReview();
              },
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _marketController,
              decoration: const InputDecoration(
                labelText: 'Market optional',
                prefixIcon: Icon(Icons.sports_soccer_outlined),
              ),
              onSubmitted: (_) => _loadReview(),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _leagueController,
              decoration: const InputDecoration(
                labelText: 'League optional',
                prefixIcon: Icon(Icons.emoji_events_outlined),
              ),
              onSubmitted: (_) => _loadReview(),
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Checkbox(
                  value: _requireOdds,
                  onChanged: (value) {
                    setState(() {
                      _requireOdds = value ?? false;
                    });

                    _loadReview();
                  },
                ),
                const Text('Require odds'),
                const Spacer(),
                TextButton.icon(
                  onPressed: () {
                    _marketController.clear();
                    _leagueController.clear();

                    setState(() {
                      _requireOdds = false;
                    });

                    _loadReview();
                  },
                  icon: const Icon(Icons.clear),
                  label: const Text('Clear'),
                ),
                const SizedBox(width: 8),
                FilledButton.icon(
                  onPressed: _loadReview,
                  icon: const Icon(Icons.search),
                  label: const Text('Load'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _recommendationSummary(ProductionReview review) {
    final summary = Map<String, dynamic>.from(
      review.recommendations['recommendation_summary'] ?? {},
    );

    final approved = review.recommendations['approved_picks'];
    final watchlist = review.recommendations['watchlist_picks'];
    final rejected = review.recommendations['rejected_picks'];

    final approvedCount = approved is List
        ? approved.length
        : summary['approved_count'] ?? summary['approved_picks'] ?? 0;

    final watchlistCount = watchlist is List
        ? watchlist.length
        : summary['watchlist_count'] ?? summary['watchlist_picks'] ?? 0;

    final rejectedCount = rejected is List
        ? rejected.length
        : summary['rejected_count'] ?? summary['rejected_picks'] ?? 0;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionTitle('Recommendation Summary'),
        const SizedBox(height: 8),
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            _miniStat(
              title: 'Approved',
              value: approvedCount,
              icon: Icons.check_circle_outline,
            ),
            _miniStat(
              title: 'Watchlist',
              value: watchlistCount,
              icon: Icons.visibility_outlined,
            ),
            _miniStat(
              title: 'Rejected',
              value: rejectedCount,
              icon: Icons.cancel_outlined,
            ),
            _miniStat(
              title: 'Groups',
              value: review.groups.length,
              icon: Icons.group_work_outlined,
            ),
          ],
        ),
      ],
    );
  }

  Widget _miniStat({
    required String title,
    required dynamic value,
    required IconData icon,
  }) {
    return SizedBox(
      width: 160,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Icon(icon),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: Theme.of(context).textTheme.labelMedium,
                    ),
                    Text(
                      '${value ?? 0}',
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _sectionTitle(String value) {
    return Text(
      value,
      style: Theme.of(context).textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.bold,
          ),
    );
  }

  Widget _errorBox(String message) {
    return Card(
      color: Colors.red.shade50,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Text(
          message,
          style: TextStyle(color: Colors.red.shade800),
        ),
      ),
    );
  }
}