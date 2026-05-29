// lib/models/prediction_dashboard_item.dart

class PredictionDashboardItem {
  final Map<String, dynamic> raw;

  PredictionDashboardItem({
    required this.raw,
  });

  factory PredictionDashboardItem.fromJson(Map<String, dynamic> json) {
    return PredictionDashboardItem(raw: json);
  }

  Map<String, dynamic> get match {
    final value = raw['match'];
    if (value is Map<String, dynamic>) return value;
    return raw;
  }

  Map<String, dynamic> get prediction {
    final value = raw['prediction'];
    if (value is Map<String, dynamic>) return value;
    return raw;
  }

  int? get matchId => _intValue([
        raw['match_id'],
        match['match_id'],
        match['id'],
        prediction['match_id'],
      ]);

  String get league => _stringValue([
        match['league'],
        raw['league'],
        prediction['league'],
      ]);

  String get homeTeam => _stringValue([
        match['home_team'],
        raw['home_team'],
        prediction['home_team'],
      ]);

  String get awayTeam => _stringValue([
        match['away_team'],
        raw['away_team'],
        prediction['away_team'],
      ]);

  String get kickoff => _stringValue([
        match['kickoff_eat'],
        match['kickoff_datetime'],
        match['kickoff_date'],
        raw['kickoff_eat'],
        raw['kickoff_datetime'],
        raw['kickoff_date'],
      ]);

  String get market => _stringValue([
        prediction['market'],
        prediction['model_market'],
        prediction['execution_market'],
        raw['market'],
      ]);

  String get predictedLabel => _stringValue([
        prediction['predicted_label'],
        prediction['selection'],
        prediction['execution_selection'],
        raw['predicted_label'],
      ]);

  String get executionMarket => _stringValue([
        prediction['execution_market'],
        prediction['market'],
        raw['execution_market'],
      ]);

  String get executionSelection => _stringValue([
        prediction['execution_selection'],
        prediction['predicted_label'],
        prediction['selection'],
        raw['execution_selection'],
      ]);

  double? get confidence => _doubleValue([
        prediction['confidence'],
        prediction['probability'],
        raw['confidence'],
      ]);

  double? get odds => _doubleValue([
        prediction['odds'],
        prediction['best_odds'],
        prediction['execution_odds'],
        raw['odds'],
      ]);

  double? get valueScore => _doubleValue([
        prediction['value_score'],
        prediction['edge'],
        raw['value_score'],
      ]);

  double? get executionScore => _doubleValue([
        prediction['execution_score'],
        prediction['bookmaker_execution_score'],
        raw['execution_score'],
      ]);

  double? get survivabilityScore => _doubleValue([
        prediction['survivability_score'],
        prediction['market_survivability_score'],
        raw['survivability_score'],
      ]);

  double? get localRealismScore => _doubleValue([
        prediction['local_realism_score'],
        prediction['kenyan_realism_score'],
        raw['local_realism_score'],
      ]);

  String get bookmaker => _stringValue([
        prediction['bookmaker'],
        prediction['odds_bookmaker'],
        prediction['provider'],
        raw['bookmaker'],
      ]);

  String get bookmakerLocality => _stringValue([
        prediction['bookmaker_locality'],
        prediction['odds_locality'],
        raw['bookmaker_locality'],
      ]);

  String get slate => _stringValue([
        prediction['slate'],
        raw['slate'],
      ]);

  bool get executionReady => _boolValue([
        prediction['execution_ready'],
        prediction['is_execution_ready'],
        prediction['ready_for_execution'],
        raw['execution_ready'],
      ]);

  bool get isKenyanPick {
    final locality = bookmakerLocality.toLowerCase();
    final bookmakerText = bookmaker.toLowerCase();
    final localScore = localRealismScore ?? 0.0;

    return locality == 'local' ||
        locality.contains('kenya') ||
        bookmakerText.contains('betika') ||
        bookmakerText.contains('sportpesa') ||
        bookmakerText.contains('odibets') ||
        bookmakerText.contains('mozzart') ||
        bookmakerText.contains('betpawa') ||
        localScore >= 0.60;
  }

  String get confidenceText {
    if (confidence == null) return '—';
    return '${(confidence! * 100).toStringAsFixed(1)}%';
  }

  String get oddsText {
    if (odds == null) return '—';
    return odds!.toStringAsFixed(2);
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