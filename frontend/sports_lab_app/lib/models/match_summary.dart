class MatchSummary {
  final int matchId;
  final String? providerFixtureId;
  final String league;
  final String season;
  final String homeTeam;
  final String awayTeam;
  final String? kickoffEat;
  final bool hasOdds;
  final bool hasPrediction;
  final int predictionCount;

  MatchSummary({
    required this.matchId,
    required this.providerFixtureId,
    required this.league,
    required this.season,
    required this.homeTeam,
    required this.awayTeam,
    required this.kickoffEat,
    required this.hasOdds,
    required this.hasPrediction,
    required this.predictionCount,
  });

  factory MatchSummary.fromJson(Map<String, dynamic> json) {
    return MatchSummary(
      matchId: json['match_id'] ?? json['id'],
      providerFixtureId: json['provider_fixture_id']?.toString(),
      league: json['league']?.toString() ?? 'Unknown League',
      season: json['season']?.toString() ?? '',
      homeTeam: json['home_team']?.toString() ?? 'Home',
      awayTeam: json['away_team']?.toString() ?? 'Away',
      kickoffEat: json['kickoff_eat']?.toString() ??
          json['kickoff_datetime']?.toString() ??
          json['kickoff_date']?.toString(),
      hasOdds: json['has_odds'] == true,
      hasPrediction: json['has_prediction'] == true ||
          json['has_predictions'] == true ||
          ((json['prediction_count'] ?? 0) > 0),
      predictionCount: json['prediction_count'] ?? 0,
    );
  }
}