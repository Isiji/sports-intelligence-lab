// lib/services/admin_api_service.dart

import 'dart:convert';

import 'package:http/http.dart' as http;

class AdminCommandItem {
  final String key;
  final String label;
  final String description;
  final String apiSafeLevel;
  final List<String> steps;

  const AdminCommandItem({
    required this.key,
    required this.label,
    required this.description,
    required this.apiSafeLevel,
    required this.steps,
  });

  factory AdminCommandItem.fromJson(Map<String, dynamic> json) {
    return AdminCommandItem(
      key: (json['key'] ?? '').toString(),
      label: (json['label'] ?? '').toString(),
      description: (json['description'] ?? '').toString(),
      apiSafeLevel: (json['api_safe_level'] ?? 'safe').toString(),
      steps: ((json['steps'] as List?) ?? [])
          .map((item) => item.toString())
          .toList(),
    );
  }
}

class AdminApiService {
  static const String baseUrl = 'http://127.0.0.1:8000';

  Future<List<AdminCommandItem>> fetchCommands() async {
    final uri = Uri.parse('$baseUrl/admin/commands');

    final response = await http.get(uri).timeout(
          const Duration(seconds: 30),
        );

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('Failed to load admin commands: ${response.body}');
    }

    final decoded = jsonDecode(response.body) as Map<String, dynamic>;
    final items = (decoded['commands'] as List?) ?? [];

    return items
        .map((item) => AdminCommandItem.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<Map<String, dynamic>> runCommand(String commandKey) async {
    final uri = Uri.parse('$baseUrl/admin/commands/run');

    final response = await http
        .post(
          uri,
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'command_key': commandKey}),
        )
        .timeout(
          const Duration(minutes: 65),
        );

    final decoded = jsonDecode(response.body) as Map<String, dynamic>;

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('Command failed: ${response.body}');
    }

    return decoded;
  }
}