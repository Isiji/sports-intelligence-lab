// lib/models/group_dashboard_item.dart

class GroupDashboardItem {
  final Map<String, dynamic> raw;

  GroupDashboardItem({
    required this.raw,
  });

  factory GroupDashboardItem.fromJson(Map<String, dynamic> json) {
    return GroupDashboardItem(raw: json);
  }

  String get groupName => _stringValue([raw['group_name']]);
  int get predictionId => _intValue([raw['prediction_id']]) ?? 0;
  int get matchId => _intValue([raw['match_id']]) ?? 0;

  String get league => _stringValue([raw['league']]);
  String get kickoffEat => _stringValue([raw['kickoff_eat']]);

  String get homeTeam => _stringValue([raw['home_team']]);
  String get awayTeam => _stringValue([raw['away_team']]);

  String get market => _stringValue([raw['market']]);
  String get predictedLabel => _stringValue([raw['predicted_label']]);

  double? get confidence => _doubleValue([raw['confidence']]);
  double? get odds => _doubleValue([raw['odds']]);
  double? get valueScore => _doubleValue([raw['value_score']]);

  String get executionMarket => _stringValue([raw['execution_market']]);
  String get executionSelection => _stringValue([raw['execution_selection']]);

  double? get executionScore => _doubleValue([raw['execution_score']]);
  double? get survivabilityScore => _doubleValue([raw['survivability_score']]);
  double? get localRealismScore => _doubleValue([raw['local_realism_score']]);

  bool get executionReady => _boolValue([raw['execution_ready']]);

  String get oddsBookmaker => _stringValue([raw['odds_bookmaker']]);
  String get bookmakerLocality => _stringValue([raw['bookmaker_locality']]);

  List<String> get executionReasons {
    final value = raw['execution_reasons'];

    if (value is List) {
      return value.map((x) => x.toString()).toList();
    }

    return const [];
  }

  String get confidenceText {
    if (confidence == null) return '—';
    return '${(confidence! * 100).toStringAsFixed(1)}%';
  }

  String get oddsText {
    if (odds == null) return '—';
    return odds!.toStringAsFixed(2);
  }

  String get valueScoreText {
    if (valueScore == null) return '—';
    return valueScore!.toStringAsFixed(3);
  }

  String get executionScoreText {
    if (executionScore == null) return '—';
    return executionScore!.toStringAsFixed(2);
  }

  String get survivabilityText {
    if (survivabilityScore == null) return '—';
    return survivabilityScore!.toStringAsFixed(2);
  }

  String get localRealismText {
    if (localRealismScore == null) return '—';
    return localRealismScore!.toStringAsFixed(2);
  }
}

class GroupDashboardSummary {
  final String groupName;
  final List<GroupDashboardItem> picks;

  GroupDashboardSummary({
    required this.groupName,
    required this.picks,
  });

  int get size => picks.length;

  double get totalOdds {
    double total = 1.0;
    var hasOdds = false;

    for (final pick in picks) {
      if (pick.odds == null) continue;
      total *= pick.odds!;
      hasOdds = true;
    }

    return hasOdds ? total : 0.0;
  }

  double get avgConfidence {
    final values = picks
        .map((x) => x.confidence)
        .whereType<double>()
        .toList();

    if (values.isEmpty) return 0.0;

    return values.reduce((a, b) => a + b) / values.length;
  }

  double get avgExecutionScore {
    final values = picks
        .map((x) => x.executionScore)
        .whereType<double>()
        .toList();

    if (values.isEmpty) return 0.0;

    return values.reduce((a, b) => a + b) / values.length;
  }

  double get avgSurvivability {
    final values = picks
        .map((x) => x.survivabilityScore)
        .whereType<double>()
        .toList();

    if (values.isEmpty) return 0.0;

    return values.reduce((a, b) => a + b) / values.length;
  }

  int get executionReadyCount {
    return picks.where((x) => x.executionReady).length;
  }

  String get riskLevel {
    if (avgConfidence >= 0.75 && avgExecutionScore >= 0.70) {
      return 'LOW';
    }

    if (avgConfidence >= 0.65 && avgExecutionScore >= 0.55) {
      return 'MEDIUM';
    }

    return 'HIGH';
  }

  String get qualityLabel {
    if (avgConfidence >= 0.75 && avgSurvivability >= 0.70) {
      return 'Strong';
    }

    if (avgConfidence >= 0.65) {
      return 'Usable';
    }

    return 'Watchlist';
  }
}

String _stringValue(List<dynamic> values) {
  for (final value in values) {
    if (value == null) continue;
    final text = value.toString().trim();
    if (text.isNotEmpty && text.toLowerCase() != 'null') return text;
  }
  return '—';
}

int? _intValue(List<dynamic> values) {
  for (final value in values) {
    if (value is int) return value;
    if (value is String) return int.tryParse(value);
  }
  return null;
}

double? _doubleValue(List<dynamic> values) {
  for (final value in values) {
    if (value == null) continue;
    if (value is num) return value.toDouble();
    final parsed = double.tryParse(value.toString());
    if (parsed != null) return parsed;
  }
  return null;
}

bool _boolValue(List<dynamic> values) {
  for (final value in values) {
    if (value is bool) return value;
    final text = value?.toString().toLowerCase().trim();
    if (text == 'true' || text == '1' || text == 'yes' || text == 'ready') {
      return true;
    }
  }
  return false;
}