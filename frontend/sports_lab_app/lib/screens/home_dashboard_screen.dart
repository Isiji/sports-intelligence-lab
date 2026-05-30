// lib/screens/home_dashboard_screen.dart

import 'package:flutter/material.dart';

class HomeDashboardScreen extends StatelessWidget {
  const HomeDashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final sections = [
      _DashboardSection(
        title: 'Core Analysis',
        items: const [
          _DashboardItem(
            title: 'Prediction Explorer',
            subtitle: 'Search fixtures, predictions, teams and leagues.',
            icon: Icons.search_outlined,
            route: '/prediction-explorer',
          ),
          _DashboardItem(
            title: 'Match Intelligence Search',
            subtitle: 'Find a match and open full intelligence.',
            icon: Icons.manage_search_outlined,
            route: '/match-intelligence',
          ),
          _DashboardItem(
            title: 'Market Alternatives Explorer',
            subtitle: 'Compare confidence across many markets.',
            icon: Icons.compare_arrows_outlined,
            route: '/market-alternatives',
          ),
          _DashboardItem(
            title: 'Jackpot / 1X2 Builder',
            subtitle: 'Home, draw and away focused workflow.',
            icon: Icons.confirmation_number_outlined,
            route: '/jackpot-builder',
          ),
        ],
      ),
      _DashboardSection(
        title: 'Slips & Picks',
        items: const [
          _DashboardItem(
            title: 'Slip Builder',
            subtitle: 'Build and inspect slips.',
            icon: Icons.receipt_long_outlined,
            route: '/slip-builder',
          ),
          _DashboardItem(
            title: 'Predictions Dashboard',
            subtitle: 'View all predictions and filters.',
            icon: Icons.dashboard_customize_outlined,
            route: '/predictions-dashboard',
          ),
          _DashboardItem(
            title: 'Execution-Ready Picks',
            subtitle: 'Picks that pass execution checks.',
            icon: Icons.verified_outlined,
            route: '/execution-ready-picks',
          ),
          _DashboardItem(
            title: 'Local / Kenyan Picks',
            subtitle: 'Kenyan bookmaker suitable picks.',
            icon: Icons.location_on_outlined,
            route: '/local-kenyan-picks',
          ),
          _DashboardItem(
            title: 'Saved Slips / Saved Analysis',
            subtitle: 'Saved slips and reviewed analysis.',
            icon: Icons.bookmark_border_outlined,
            route: '/saved-slips-analysis',
          ),
        ],
      ),
      _DashboardSection(
        title: 'Groups & Production',
        items: const [
          _DashboardItem(
            title: 'Groups Dashboard',
            subtitle: 'Generated groups and portfolio slips.',
            icon: Icons.groups_outlined,
            route: '/groups-dashboard',
          ),
          _DashboardItem(
            title: 'Group Details',
            subtitle: 'Inspect group picks and risk.',
            icon: Icons.account_tree_outlined,
            route: '/group-details',
          ),
          _DashboardItem(
            title: 'Production Review',
            subtitle: 'Slate quality and readiness review.',
            icon: Icons.fact_check_outlined,
            route: '/production-review',
          ),
        ],
      ),
      _DashboardSection(
        title: 'Research & Intelligence',
        items: const [
          _DashboardItem(
            title: 'Backtests',
            subtitle: 'ROI, calibration and history.',
            icon: Icons.history_outlined,
            route: '/backtests',
          ),
          _DashboardItem(
            title: 'Intelligence Reports',
            subtitle: 'Market, league and execution reports.',
            icon: Icons.psychology_outlined,
            route: '/intelligence-reports',
          ),
          _DashboardItem(
            title: 'League / Odds Coverage',
            subtitle: 'Bookmaker and market coverage.',
            icon: Icons.analytics_outlined,
            route: '/league-odds-coverage',
          ),
        ],
      ),
      _DashboardSection(
        title: 'Admin & Automation',
        items: const [
          _DashboardItem(
            title: 'Command Center / Admin Runner',
            subtitle: 'Run backend CLI workflows.',
            icon: Icons.terminal_outlined,
            route: '/command-center',
          ),
          _DashboardItem(
            title: 'Data Ingestion',
            subtitle: 'Fixtures, odds and stats ingestion.',
            icon: Icons.cloud_download_outlined,
            route: '/data-ingestion',
          ),
          _DashboardItem(
            title: 'Model Training',
            subtitle: 'Features, training and intelligence rebuilds.',
            icon: Icons.model_training_outlined,
            route: '/model-training',
          ),
          _DashboardItem(
            title: 'Odds / Stats Updates',
            subtitle: 'Refresh odds, stats and results.',
            icon: Icons.update_outlined,
            route: '/odds-stats-updates',
          ),
          _DashboardItem(
            title: 'Settings',
            subtitle: 'API, filters and preferences.',
            icon: Icons.settings_outlined,
            route: '/settings',
          ),
          _DashboardItem(
            title: 'Automation Center',
            subtitle: 'Scheduled server jobs, history and run controls.',
            icon: Icons.schedule_outlined,
            route: '/automation-center',
          ), 
        ],
      ),
    ];

    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FB),
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            final crossAxisCount = constraints.maxWidth >= 1100
                ? 4
                : constraints.maxWidth >= 760
                    ? 3
                    : 2;

            return ListView(
              padding: const EdgeInsets.all(16),
              children: [
                const _DashboardHeader(),
                const SizedBox(height: 18),
                for (final section in sections) ...[
                  _SectionTitle(title: section.title),
                  const SizedBox(height: 10),
                  GridView.builder(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: section.items.length,
                    gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: crossAxisCount,
                      crossAxisSpacing: 12,
                      mainAxisSpacing: 12,
                      childAspectRatio: constraints.maxWidth < 420 ? 1.05 : 1.25,
                    ),
                    itemBuilder: (context, index) {
                      return _DashboardCard(item: section.items[index]);
                    },
                  ),
                  const SizedBox(height: 24),
                ],
              ],
            );
          },
        ),
      ),
    );
  }
}

class _DashboardHeader extends StatelessWidget {
  const _DashboardHeader();

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
        borderRadius: BorderRadius.circular(28),
      ),
      child: Row(
        children: [
          Container(
            width: 54,
            height: 54,
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.12),
              borderRadius: BorderRadius.circular(18),
            ),
            child: const Icon(
              Icons.sports_soccer,
              color: Colors.white,
              size: 30,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Sports Intelligence Lab',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w900,
                      ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Predictions, match analysis, slips, groups, execution, research and admin workflows.',
                  style: TextStyle(
                    color: Colors.white.withOpacity(0.82),
                    height: 1.35,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final String title;

  const _SectionTitle({
    required this.title,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 5,
          height: 28,
          decoration: BoxDecoration(
            color: const Color(0xFF2563EB),
            borderRadius: BorderRadius.circular(99),
          ),
        ),
        const SizedBox(width: 10),
        Text(
          title,
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w900,
              ),
        ),
      ],
    );
  }
}

class _DashboardCard extends StatelessWidget {
  final _DashboardItem item;

  const _DashboardCard({
    required this.item,
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
      child: InkWell(
        borderRadius: BorderRadius.circular(22),
        onTap: () => Navigator.of(context).pushNamed(item.route),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                item.icon,
                size: 30,
                color: const Color(0xFF2563EB),
              ),
              const Spacer(),
              Text(
                item.title,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w900,
                      color: const Color(0xFF0F172A),
                    ),
              ),
              const SizedBox(height: 5),
              Text(
                item.subtitle,
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Colors.black54,
                      height: 1.25,
                      fontWeight: FontWeight.w500,
                    ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _DashboardSection {
  final String title;
  final List<_DashboardItem> items;

  const _DashboardSection({
    required this.title,
    required this.items,
  });
}

class _DashboardItem {
  final String title;
  final String subtitle;
  final IconData icon;
  final String route;

  const _DashboardItem({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.route,
  });
}