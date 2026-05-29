// lib/screens/groups_dashboard_screen.dart

import 'package:flutter/material.dart';

import '../models/group_dashboard_item.dart';
import '../services/group_api_service.dart';
import 'match_intelligence_screen.dart';

class GroupsDashboardScreen extends StatefulWidget {
  const GroupsDashboardScreen({super.key});

  @override
  State<GroupsDashboardScreen> createState() => _GroupsDashboardScreenState();
}

class _GroupsDashboardScreenState extends State<GroupsDashboardScreen> {
  final GroupApiService _api = const GroupApiService();
  final TextEditingController _slateController = TextEditingController();

  bool _isLoading = false;
  bool _isCreating = false;
  bool _requireOdds = false;

  double _minConfidence = 0.65;
  double _minGroupOdds = 3.0;

  String? _error;
  List<GroupDashboardItem> _items = [];

  @override
  void initState() {
    super.initState();
    _loadGroups();
  }

  @override
  void dispose() {
    _slateController.dispose();
    super.dispose();
  }

  List<GroupDashboardSummary> get _groups {
    final grouped = <String, List<GroupDashboardItem>>{};

    for (final item in _items) {
      grouped.putIfAbsent(item.groupName, () => []).add(item);
    }

    final summaries = grouped.entries
        .map(
          (entry) => GroupDashboardSummary(
            groupName: entry.key,
            picks: entry.value,
          ),
        )
        .toList();

    summaries.sort((a, b) => a.groupName.compareTo(b.groupName));
    return summaries;
  }

  Future<void> _loadGroups() async {
    if (_isLoading) return;

    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final items = await _api.listGroups(
        slate: _slateController.text,
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

  Future<void> _createGroups() async {
    if (_isCreating) return;

    setState(() {
      _isCreating = true;
      _error = null;
    });

    try {
      await _api.createGroups(
        slate: _slateController.text,
        minConfidence: _minConfidence,
        minGroupOdds: _minGroupOdds,
        requireOdds: _requireOdds,
      );

      await _loadGroups();

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Groups created successfully.'),
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
        _isCreating = false;
      });
    }
  }

  void _openMatch(GroupDashboardItem item) {
    if (item.matchId <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('This group pick has no valid match ID.'),
        ),
      );
      return;
    }

    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => MatchIntelligenceScreen(matchId: item.matchId),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final groups = _groups;
    final totalPicks = _items.length;
    final executionReady = _items.where((x) => x.executionReady).length;

    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FB),
      appBar: AppBar(
        title: const Text('Groups Dashboard'),
        backgroundColor: const Color(0xFF0F172A),
        foregroundColor: Colors.white,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () {
            if (Navigator.of(context).canPop()) {
              Navigator.of(context).pop();
            } else {
              Navigator.of(context).pushReplacementNamed('/');
            }
          },
        ),
        actions: [
          IconButton(
            tooltip: 'Home',
            onPressed: () {
              Navigator.of(context).pushNamedAndRemoveUntil('/', (_) => false);
            },
            icon: const Icon(Icons.home_outlined),
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            _Header(
              groupCount: groups.length,
              pickCount: totalPicks,
              executionReadyCount: executionReady,
              isLoading: _isLoading,
              onReload: _loadGroups,
            ),
            Expanded(
              child: RefreshIndicator(
                onRefresh: _loadGroups,
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
                  children: [
                    _ControlPanel(
                      slateController: _slateController,
                      minConfidence: _minConfidence,
                      minGroupOdds: _minGroupOdds,
                      requireOdds: _requireOdds,
                      isLoading: _isLoading,
                      isCreating: _isCreating,
                      onLoad: _loadGroups,
                      onCreate: _createGroups,
                      onMinConfidenceChanged: (value) {
                        setState(() {
                          _minConfidence = value;
                        });
                      },
                      onMinGroupOddsChanged: (value) {
                        setState(() {
                          _minGroupOdds = value;
                        });
                      },
                      onRequireOddsChanged: (value) {
                        setState(() {
                          _requireOdds = value;
                        });
                      },
                    ),
                    const SizedBox(height: 14),
                    if (_isLoading || _isCreating)
                      const LinearProgressIndicator(),
                    if (_error != null) ...[
                      const SizedBox(height: 12),
                      _ErrorBox(
                        message: _error!,
                        onRetry: _loadGroups,
                      ),
                    ],
                    const SizedBox(height: 14),
                    _SectionTitle(
                      title: 'Generated Groups',
                      subtitle:
                          'Inspect group quality, risk level, combined odds and execution readiness.',
                    ),
                    const SizedBox(height: 12),
                    if (groups.isEmpty && !_isLoading && _error == null)
                      const _EmptyState()
                    else
                      ...groups.map(
                        (group) => _GroupCard(
                          group: group,
                          onOpenMatch: _openMatch,
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
  final int groupCount;
  final int pickCount;
  final int executionReadyCount;
  final bool isLoading;
  final VoidCallback onReload;

  const _Header({
    required this.groupCount,
    required this.pickCount,
    required this.executionReadyCount,
    required this.isLoading,
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
              const Icon(Icons.groups_outlined, color: Colors.white),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  'Groups Dashboard',
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
            'Portfolio groups, grouped picks, risk level, odds and execution intelligence.',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Colors.white.withOpacity(0.82),
                ),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(child: _StatTile(label: 'Groups', value: '$groupCount')),
              const SizedBox(width: 10),
              Expanded(child: _StatTile(label: 'Picks', value: '$pickCount')),
              const SizedBox(width: 10),
              Expanded(
                child: _StatTile(
                  label: 'Ready',
                  value: '$executionReadyCount',
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ControlPanel extends StatelessWidget {
  final TextEditingController slateController;
  final double minConfidence;
  final double minGroupOdds;
  final bool requireOdds;
  final bool isLoading;
  final bool isCreating;
  final VoidCallback onLoad;
  final VoidCallback onCreate;
  final ValueChanged<double> onMinConfidenceChanged;
  final ValueChanged<double> onMinGroupOddsChanged;
  final ValueChanged<bool> onRequireOddsChanged;

  const _ControlPanel({
    required this.slateController,
    required this.minConfidence,
    required this.minGroupOdds,
    required this.requireOdds,
    required this.isLoading,
    required this.isCreating,
    required this.onLoad,
    required this.onCreate,
    required this.onMinConfidenceChanged,
    required this.onMinGroupOddsChanged,
    required this.onRequireOddsChanged,
  });

  @override
  Widget build(BuildContext context) {
    final disabled = isLoading || isCreating;

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
            TextField(
              controller: slateController,
              decoration: InputDecoration(
                labelText: 'Slate',
                hintText: 'Leave empty to use backend default slate',
                prefixIcon: const Icon(Icons.list_alt_outlined),
                filled: true,
                fillColor: const Color(0xFFF8FAFC),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
              ),
            ),
            const SizedBox(height: 12),
            _SliderRow(
              label: 'Min confidence',
              value: minConfidence,
              min: 0.50,
              max: 0.95,
              divisions: 9,
              display: '${(minConfidence * 100).round()}%',
              disabled: disabled,
              onChanged: onMinConfidenceChanged,
            ),
            const SizedBox(height: 6),
            _SliderRow(
              label: 'Min group odds',
              value: minGroupOdds,
              min: 1.0,
              max: 15.0,
              divisions: 28,
              display: minGroupOdds.toStringAsFixed(1),
              disabled: disabled,
              onChanged: onMinGroupOddsChanged,
            ),
            SwitchListTile(
              value: requireOdds,
              onChanged: disabled ? null : onRequireOddsChanged,
              title: const Text('Require odds'),
              subtitle: const Text('Only group picks with odds.'),
              contentPadding: EdgeInsets.zero,
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: disabled ? null : onLoad,
                    icon: const Icon(Icons.download_outlined),
                    label: const Text('Load'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: disabled ? null : onCreate,
                    icon: isCreating
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.auto_awesome_outlined),
                    label: Text(isCreating ? 'Creating...' : 'Create'),
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

class _SliderRow extends StatelessWidget {
  final String label;
  final double value;
  final double min;
  final double max;
  final int divisions;
  final String display;
  final bool disabled;
  final ValueChanged<double> onChanged;

  const _SliderRow({
    required this.label,
    required this.value,
    required this.min,
    required this.max,
    required this.divisions,
    required this.display,
    required this.disabled,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Row(
          children: [
            Text(
              label,
              style: const TextStyle(fontWeight: FontWeight.w800),
            ),
            const Spacer(),
            Text(
              display,
              style: const TextStyle(fontWeight: FontWeight.w900),
            ),
          ],
        ),
        Slider(
          value: value,
          min: min,
          max: max,
          divisions: divisions,
          label: display,
          onChanged: disabled ? null : onChanged,
        ),
      ],
    );
  }
}

class _GroupCard extends StatelessWidget {
  final GroupDashboardSummary group;
  final ValueChanged<GroupDashboardItem> onOpenMatch;

  const _GroupCard({
    required this.group,
    required this.onOpenMatch,
  });

  @override
  Widget build(BuildContext context) {
    final riskColor = _riskColor(group.riskLevel);

    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: Colors.black.withOpacity(0.06)),
      ),
      child: ExpansionTile(
        tilePadding: const EdgeInsets.fromLTRB(14, 8, 14, 8),
        childrenPadding: const EdgeInsets.fromLTRB(14, 0, 14, 14),
        title: Row(
          children: [
            Expanded(
              child: Text(
                group.groupName,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w900,
                    ),
              ),
            ),
            _Pill(text: group.riskLevel, color: riskColor),
          ],
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 10),
          child: Column(
            children: [
              Row(
                children: [
                  Expanded(
                    child: _Metric(
                      label: 'Quality',
                      value: group.qualityLabel,
                    ),
                  ),
                  Expanded(
                    child: _Metric(
                      label: 'Picks',
                      value: '${group.size}',
                    ),
                  ),
                  Expanded(
                    child: _Metric(
                      label: 'Total odds',
                      value: group.totalOdds == 0.0
                          ? '—'
                          : group.totalOdds.toStringAsFixed(2),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: _Metric(
                      label: 'Avg conf',
                      value: '${(group.avgConfidence * 100).toStringAsFixed(1)}%',
                    ),
                  ),
                  Expanded(
                    child: _Metric(
                      label: 'Execution',
                      value: group.avgExecutionScore.toStringAsFixed(2),
                    ),
                  ),
                  Expanded(
                    child: _Metric(
                      label: 'Ready',
                      value: '${group.executionReadyCount}/${group.size}',
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        children: [
          const SizedBox(height: 8),
          ...group.picks.map(
            (pick) => _GroupPickCard(
              item: pick,
              onOpenMatch: () => onOpenMatch(pick),
            ),
          ),
        ],
      ),
    );
  }
}

class _GroupPickCard extends StatelessWidget {
  final GroupDashboardItem item;
  final VoidCallback onOpenMatch;

  const _GroupPickCard({
    required this.item,
    required this.onOpenMatch,
  });

  @override
  Widget build(BuildContext context) {
    final readyColor =
        item.executionReady ? const Color(0xFF166534) : const Color(0xFF92400E);

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.black.withOpacity(0.05)),
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
              Text(
                item.confidenceText,
                style: const TextStyle(
                  fontWeight: FontWeight.w900,
                  color: Color(0xFF0F172A),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            '${item.homeTeam} vs ${item.awayTeam}',
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 4),
          Text(
            item.kickoffEat,
            style: const TextStyle(
              color: Colors.black54,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(child: _Metric(label: 'Market', value: _label(item.market))),
              Expanded(
                child: _Metric(
                  label: 'Pick',
                  value: _label(item.predictedLabel),
                ),
              ),
              Expanded(child: _Metric(label: 'Odds', value: item.oddsText)),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
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
              Expanded(
                child: _Metric(
                  label: 'Local',
                  value: item.localRealismText,
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
          _InfoRow(label: 'Bookmaker', value: item.oddsBookmaker),
          _InfoRow(label: 'Locality', value: item.bookmakerLocality),
          if (item.executionReasons.isNotEmpty) ...[
            const SizedBox(height: 8),
            ...item.executionReasons.take(3).map(
                  (reason) => _ReasonText(text: reason),
                ),
          ],
          const SizedBox(height: 10),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: onOpenMatch,
              icon: const Icon(Icons.analytics_outlined),
              label: const Text('Open Match Intelligence'),
            ),
          ),
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

class _ReasonText extends StatelessWidget {
  final String text;

  const _ReasonText({
    required this.text,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xFFFFFBEB),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFF92400E).withOpacity(0.18)),
      ),
      child: Text(
        text,
        style: const TextStyle(
          color: Color(0xFF92400E),
          fontWeight: FontWeight.w700,
        ),
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
            'Could not load groups',
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
            Icons.groups_outlined,
            size: 42,
            color: Colors.black45,
          ),
          SizedBox(height: 10),
          Text(
            'No groups found',
            style: TextStyle(
              fontWeight: FontWeight.w900,
              color: Color(0xFF0F172A),
            ),
          ),
          SizedBox(height: 4),
          Text(
            'Create groups first or enter the correct slate.',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.black54),
          ),
        ],
      ),
    );
  }
}

Color _riskColor(String risk) {
  switch (risk.toUpperCase()) {
    case 'LOW':
      return const Color(0xFF166534);
    case 'MEDIUM':
      return const Color(0xFF92400E);
    default:
      return const Color(0xFF9F1239);
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