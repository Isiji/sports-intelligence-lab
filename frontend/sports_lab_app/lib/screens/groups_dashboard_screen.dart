// lib/screens/groups_dashboard_screen.dart

import 'package:flutter/material.dart';

import '../models/group_dashboard_item.dart';
import '../services/group_api_service.dart';
import 'group_details_screen.dart';

class GroupsDashboardScreen extends StatefulWidget {
  const GroupsDashboardScreen({super.key});

  @override
  State<GroupsDashboardScreen> createState() => _GroupsDashboardScreenState();
}

class _GroupsDashboardScreenState extends State<GroupsDashboardScreen> {
  final GroupApiService _api = const GroupApiService();

  bool _isLoadingSlates = false;
  bool _isLoadingGroups = false;

  String? _error;
  String? _selectedSlate;

  List<GroupSlate> _slates = [];
  List<GroupDashboardItem> _items = [];

  @override
  void initState() {
    super.initState();
    _loadSlatesAndDefaultGroups();
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

  Future<void> _loadSlatesAndDefaultGroups() async {
    setState(() {
      _isLoadingSlates = true;
      _isLoadingGroups = true;
      _error = null;
    });

    try {
      final slates = await _api.listGroupSlates();

      if (!mounted) return;

      final selected = slates.isNotEmpty ? slates.first.slate : null;

      setState(() {
        _slates = slates;
        _selectedSlate = selected;
      });

      if (selected != null) {
        await _loadGroupsForSlate(selected);
      } else {
        setState(() {
          _items = [];
        });
      }
    } catch (e) {
      if (!mounted) return;

      setState(() {
        _error = e.toString();
      });
    } finally {
      if (!mounted) return;

      setState(() {
        _isLoadingSlates = false;
        _isLoadingGroups = false;
      });
    }
  }

  Future<void> _loadGroupsForSlate(String slate) async {
    setState(() {
      _isLoadingGroups = true;
      _error = null;
    });

    try {
      final items = await _api.listGroups(slate: slate);

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
        _isLoadingGroups = false;
      });
    }
  }

  Future<void> _reload() async {
    if (_selectedSlate == null) {
      await _loadSlatesAndDefaultGroups();
      return;
    }

    await _loadGroupsForSlate(_selectedSlate!);
  }

  void _openGroup(GroupDashboardSummary group) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => GroupDetailsScreen(group: group),
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
            tooltip: 'Reload slates',
            onPressed: _isLoadingSlates ? null : _loadSlatesAndDefaultGroups,
            icon: const Icon(Icons.sync_outlined),
          ),
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
              slateCount: _slates.length,
              groupCount: groups.length,
              pickCount: totalPicks,
              executionReadyCount: executionReady,
            ),
            Expanded(
              child: RefreshIndicator(
                onRefresh: _reload,
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
                  children: [
                    _SlateSelector(
                      slates: _slates,
                      selectedSlate: _selectedSlate,
                      isLoading: _isLoadingSlates || _isLoadingGroups,
                      onChanged: (value) async {
                        if (value == null) return;

                        setState(() {
                          _selectedSlate = value;
                        });

                        await _loadGroupsForSlate(value);
                      },
                    ),
                    const SizedBox(height: 14),
                    if (_isLoadingSlates || _isLoadingGroups)
                      const LinearProgressIndicator(),
                    if (_error != null) ...[
                      const SizedBox(height: 12),
                      _ErrorBox(
                        message: _error!,
                        onRetry: _loadSlatesAndDefaultGroups,
                      ),
                    ],
                    const SizedBox(height: 14),
                    _SectionTitle(
                      title: 'Generated Groups',
                      subtitle:
                          'These are saved groups. Group creation belongs in Admin / Command Center.',
                    ),
                    const SizedBox(height: 12),
                    if (_slates.isEmpty && !_isLoadingSlates && _error == null)
                      const _EmptySlatesState()
                    else if (groups.isEmpty && !_isLoadingGroups && _error == null)
                      const _EmptyGroupsState()
                    else
                      ...groups.map(
                        (group) => _GroupCard(
                          group: group,
                          onTap: () => _openGroup(group),
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
  final int slateCount;
  final int groupCount;
  final int pickCount;
  final int executionReadyCount;

  const _Header({
    required this.slateCount,
    required this.groupCount,
    required this.pickCount,
    required this.executionReadyCount,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(18, 18, 18, 18),
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          colors: [Color(0xFF0F172A), Color(0xFF1E3A8A)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.vertical(bottom: Radius.circular(28)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Saved portfolio groups by slate. No manual slate typing required.',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Colors.white.withOpacity(0.82),
                ),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(child: _StatTile(label: 'Slates', value: '$slateCount')),
              const SizedBox(width: 10),
              Expanded(child: _StatTile(label: 'Groups', value: '$groupCount')),
              const SizedBox(width: 10),
              Expanded(child: _StatTile(label: 'Picks', value: '$pickCount')),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: _StatTile(
                  label: 'Execution Ready',
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

class _SlateSelector extends StatelessWidget {
  final List<GroupSlate> slates;
  final String? selectedSlate;
  final bool isLoading;
  final ValueChanged<String?> onChanged;

  const _SlateSelector({
    required this.slates,
    required this.selectedSlate,
    required this.isLoading,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 0,
      color: Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(24),
        side: BorderSide(color: Colors.black.withOpacity(0.06)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: DropdownButtonFormField<String>(
          initialValue: selectedSlate,
          items: slates
              .map(
                (item) => DropdownMenuItem<String>(
                  value: item.slate,
                  child: Text(
                    '${item.slate}  •  ${item.groupCount} groups  •  ${item.pickCount} picks',
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              )
              .toList(),
          onChanged: isLoading ? null : onChanged,
          decoration: InputDecoration(
            labelText: 'Saved group slate',
            prefixIcon: const Icon(Icons.folder_copy_outlined),
            filled: true,
            fillColor: const Color(0xFFF8FAFC),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(16),
            ),
          ),
        ),
      ),
    );
  }
}

class _GroupCard extends StatelessWidget {
  final GroupDashboardSummary group;
  final VoidCallback onTap;

  const _GroupCard({
    required this.group,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final riskColor = _riskColor(group.riskLevel);

    return InkWell(
      borderRadius: BorderRadius.circular(24),
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 14),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(24),
          border: Border.all(color: Colors.black.withOpacity(0.06)),
        ),
        child: Column(
          children: [
            Row(
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
                const SizedBox(width: 6),
                const Icon(Icons.chevron_right),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(child: _Metric(label: 'Quality', value: group.qualityLabel)),
                Expanded(child: _Metric(label: 'Picks', value: '${group.size}')),
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

class _EmptySlatesState extends StatelessWidget {
  const _EmptySlatesState();

  @override
  Widget build(BuildContext context) {
    return const _EmptyBox(
      title: 'No saved group slates found',
      subtitle: 'Create groups from Admin / Command Center first.',
    );
  }
}

class _EmptyGroupsState extends StatelessWidget {
  const _EmptyGroupsState();

  @override
  Widget build(BuildContext context) {
    return const _EmptyBox(
      title: 'No groups found for this slate',
      subtitle: 'Choose another saved slate.',
    );
  }
}

class _EmptyBox extends StatelessWidget {
  final String title;
  final String subtitle;

  const _EmptyBox({
    required this.title,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: Colors.black.withOpacity(0.06)),
      ),
      child: Column(
        children: [
          const Icon(Icons.groups_outlined, size: 42, color: Colors.black45),
          const SizedBox(height: 10),
          Text(
            title,
            style: const TextStyle(
              fontWeight: FontWeight.w900,
              color: Color(0xFF0F172A),
            ),
          ),
          const SizedBox(height: 4),
          Text(
            subtitle,
            textAlign: TextAlign.center,
            style: const TextStyle(color: Colors.black54),
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