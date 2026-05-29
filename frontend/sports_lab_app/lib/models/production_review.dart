// lib/models/production_review.dart

class ProductionReview {
  final String slate;
  final Map<String, dynamic> summary;
  final Map<String, dynamic> productionHealth;
  final List<Map<String, dynamic>> rankedPicks;
  final Map<String, dynamic> recommendations;
  final List<Map<String, dynamic>> groups;

  const ProductionReview({
    required this.slate,
    required this.summary,
    required this.productionHealth,
    required this.rankedPicks,
    required this.recommendations,
    required this.groups,
  });

  factory ProductionReview.fromJson(Map<String, dynamic> json) {
    return ProductionReview(
      slate: '${json['slate'] ?? ''}',
      summary: Map<String, dynamic>.from(json['summary'] ?? {}),
      productionHealth: Map<String, dynamic>.from(
        json['production_health'] ?? {},
      ),
      rankedPicks: (json['ranked_picks'] as List? ?? [])
          .whereType<Map>()
          .map((e) => Map<String, dynamic>.from(e))
          .toList(),
      recommendations: Map<String, dynamic>.from(
        json['recommendations'] ?? {},
      ),
      groups: (json['groups'] as List? ?? [])
          .whereType<Map>()
          .map((e) => Map<String, dynamic>.from(e))
          .toList(),
    );
  }
}