// lib/services/admin_api_service.dart

import 'dart:convert';

import 'package:http/http.dart' as http;

class AdminSeasonInfo {
  final int activeSeason;
  final List<int> availableSeasons;

  const AdminSeasonInfo({
    required this.activeSeason,
    required this.availableSeasons,
  });

  factory AdminSeasonInfo.fromJson(Map<String, dynamic> json) {
    return AdminSeasonInfo(
      activeSeason: int.tryParse((json['active_season'] ?? '2026').toString()) ?? 2026,
      availableSeasons: ((json['available_seasons'] as List?) ?? [])
          .map((item) => int.tryParse(item.toString()) ?? 2026)
          .toList(),
    );
  }
}

class AdminCommandItem {
  final String key;
  final String label;
  final String description;
  final String apiSafeLevel;
  final String category;
  final List<String> steps;

  const AdminCommandItem({
    required this.key,
    required this.label,
    required this.description,
    required this.apiSafeLevel,
    required this.category,
    required this.steps,
  });

  factory AdminCommandItem.fromJson(Map<String, dynamic> json) {
    return AdminCommandItem(
      key: (json['key'] ?? '').toString(),
      label: (json['label'] ?? '').toString(),
      description: (json['description'] ?? '').toString(),
      apiSafeLevel: (json['api_safe_level'] ?? 'safe').toString(),
      category: (json['category'] ?? 'General').toString(),
      steps: ((json['steps'] as List?) ?? []).map((item) => item.toString()).toList(),
    );
  }
}

class AdminApiService {
  static const String baseUrl = 'http://127.0.0.1:8000';

  Future<AdminSeasonInfo> fetchSeason() async {
    final response = await http.get(Uri.parse('$baseUrl/admin/season'));

    final decoded = jsonDecode(response.body) as Map<String, dynamic>;

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('Failed to load season: ${response.body}');
    }

    return AdminSeasonInfo.fromJson(decoded);
  }

  Future<AdminSeasonInfo> saveSeason(int season) async {
    final response = await http.post(
      Uri.parse('$baseUrl/admin/season'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'season': season}),
    );

    final decoded = jsonDecode(response.body) as Map<String, dynamic>;

    if (response.statusCode < 200 || response.statusCode >= 300 || decoded['ok'] != true) {
      throw Exception(decoded['error'] ?? 'Failed to save season');
    }

    return AdminSeasonInfo.fromJson(decoded);
  }

  Future<List<AdminCommandItem>> fetchCommands() async {
    final response = await http.get(Uri.parse('$baseUrl/admin/commands'));

    final decoded = jsonDecode(response.body) as Map<String, dynamic>;

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('Failed to load admin commands: ${response.body}');
    }

    final items = (decoded['commands'] as List?) ?? [];

    return items.map((item) => AdminCommandItem.fromJson(item as Map<String, dynamic>)).toList();
  }

  Future<Map<String, dynamic>> runCommand(String commandKey) async {
    final response = await http
        .post(
          Uri.parse('$baseUrl/admin/commands/run'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'command_key': commandKey}),
        )
        .timeout(const Duration(minutes: 65));

    final decoded = jsonDecode(response.body) as Map<String, dynamic>;

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('Command failed: ${response.body}');
    }

    return decoded;
  }
}