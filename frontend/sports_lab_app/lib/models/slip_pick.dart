// lib/models/slip_pick.dart

import 'match_intelligence.dart';

class SlipPick {
  final int? matchId;
  final String league;
  final String homeTeam;
  final String awayTeam;
  final String kickoff;
  final String market;
  final String selection;
  final double? confidence;
  final double? odds;
  final double? executionScore;
  final double? survivabilityScore;
  final double? localRealismScore;
  final String bookmaker;
  final String bookmakerLocality;
  final String mode;

  SlipPick({
    required this.matchId,
    required this.league,
    required this.homeTeam,
    required this.awayTeam,
    required this.kickoff,
    required this.market,
    required this.selection,
    required this.confidence,
    required this.odds,
    required this.executionScore,
    required this.survivabilityScore,
    required this.localRealismScore,
    required this.bookmaker,
    required this.bookmakerLocality,
    required this.mode,
  });

  factory SlipPick.fromMarketAlternative({
    required MatchIntelligence match,
    required MarketAlternative item,
    String mode = 'normal',
  }) {
    return SlipPick(
      matchId: match.matchId,
      league: match.league,
      homeTeam: match.homeTeam,
      awayTeam: match.awayTeam,
      kickoff: match.kickoff,
      market: item.executionMarket,
      selection: item.executionSelection,
      confidence: item.confidence,
      odds: item.odds,
      executionScore: item.executionScore,
      survivabilityScore: item.survivabilityScore,
      localRealismScore: item.localRealismScore,
      bookmaker: item.bookmaker,
      bookmakerLocality: item.bookmakerLocality,
      mode: mode,
    );
  }

  double get effectiveOdds => odds ?? 1.0;

  String get matchTitle => '$homeTeam vs $awayTeam';

  String get kenyaGrade {
    final score = localRealismScore;

    if (bookmakerLocality.toUpperCase() == 'LOCAL' &&
        score != null &&
        score >= 0.75) {
      return 'A';
    }

    if (score == null) return 'Unknown';
    if (score >= 0.75) return 'A';
    if (score >= 0.60) return 'B';
    if (score >= 0.45) return 'C';
    if (score >= 0.30) return 'D';

    return 'Weak';
  }
}