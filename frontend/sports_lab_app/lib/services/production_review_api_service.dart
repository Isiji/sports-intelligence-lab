// lib/services/production_review_api_service.dart

import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/production_review.dart';

class ProductionReviewApiService {
  const ProductionReviewApiService();

  static const Duration _timeout = Duration(seconds: 90);

  Future<List<String>> getAvailableSlates() async {
    final candidates = [
      '${ApiConfig.baseUrl}/groups/slates',
      '${ApiConfig.baseUrl}/predictions/slates',
      '${ApiConfig.baseUrl}/groups/available-slates',
    ];

    for (final url in candidates) {
      try {
        final response = await http.get(Uri.parse(url)).timeout(_timeout);

        if (response.statusCode != 200) {
          continue;
        }

        final decoded = jsonDecode(response.body);

        final List<dynamic> raw;

        if (decoded is List) {
          raw = decoded;
        } else if (decoded is Map<String, dynamic>) {
          raw = decoded['slates'] ??
              decoded['items'] ??
              decoded['data'] ??
              decoded['results'] ??
              [];
        } else {
          raw = [];
        }

        final slates = raw
            .map((e) {
              if (e is String) return e;
              if (e is Map) {
                return '${e['slate'] ?? e['name'] ?? e['slate_name'] ?? ''}';
              }
              return '';
            })
            .where((e) => e.trim().isNotEmpty)
            .toSet()
            .toList();

        slates.sort((a, b) => b.compareTo(a));
        return slates;
      } catch (_) {
        continue;
      }
    }

    return [];
  }

  Future<ProductionReview> getProductionReview({
    String? slate,
    String? market,
    String? league,
    bool requireOdds = false,
    int limit = 100,
  }) async {
    final query = <String, String>{
      'require_odds': requireOdds.toString(),
      'limit': limit.toString(),
    };

    if (slate != null && slate.trim().isNotEmpty) {
      query['slate'] = slate.trim();
    }

    if (market != null && market.trim().isNotEmpty) {
      query['market'] = market.trim();
    }

    if (league != null && league.trim().isNotEmpty) {
      query['league'] = league.trim();
    }

    final uri = Uri.parse(
      '${ApiConfig.baseUrl}/production/review',
    ).replace(queryParameters: query);

    final response = await http.get(uri).timeout(_timeout);

    if (response.statusCode != 200) {
      throw Exception(response.body);
    }

    final decoded = jsonDecode(response.body);

    if (decoded is! Map<String, dynamic>) {
      throw Exception('Invalid production review response');
    }

    return ProductionReview.fromJson(decoded);
  }
}