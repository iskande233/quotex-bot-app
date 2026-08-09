import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

class ApiService {
  static const String defaultBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://quotex-bot-app-2.onrender.com',
  );
  static String _baseUrl = defaultBaseUrl;

  static String _normalizeBaseUrl(String url) {
    var clean = url
        .trim()
        .replaceAll(RegExp(r'\s+'), '')
        .replaceAll('[', '')
        .replaceAll(']', '')
        .replaceAll('(', '')
        .replaceAll(')', '')
        .replaceAll(RegExp(r'/+$'), '');
    if (clean.isNotEmpty && !clean.startsWith('http://') && !clean.startsWith('https://')) {
      clean = 'https://$clean';
    }
    try {
      final uri = Uri.parse(clean);
      if (uri.hasScheme && uri.host.isNotEmpty) {
        return '${uri.scheme}://${uri.host}${uri.hasPort ? ':${uri.port}' : ''}';
      }
    } catch (_) {}
    return clean.isEmpty ? defaultBaseUrl : clean;
  }

  static String get baseUrl => _baseUrl;
  static String get wsUrl {
    final clean = _normalizeBaseUrl(_baseUrl);
    if (clean.startsWith('https://')) return clean.replaceFirst('https://', 'wss://') + '/ws';
    if (clean.startsWith('http://')) return clean.replaceFirst('http://', 'ws://') + '/ws';
    return 'ws://$clean/ws';
  }

  static Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString('api_base_url');
    _baseUrl = _normalizeBaseUrl(saved == null || saved.trim().isEmpty ? defaultBaseUrl : saved);
    await prefs.setString('api_base_url', _baseUrl);
  }

  static Future<void> setBaseUrl(String url) async {
    _baseUrl = _normalizeBaseUrl(url);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('api_base_url', _baseUrl);
  }

  static WebSocketChannel connectWs() => WebSocketChannel.connect(Uri.parse(wsUrl));

  static Future<Map<String, dynamic>> login({required String email, required String password, required String accountType, String otpCode = ''}) async {
    final res = await http.post(Uri.parse('$baseUrl/api/v1/auth/login'), headers: {'Content-Type': 'application/json'}, body: jsonEncode({'email': email, 'password': password, 'account_type': accountType, 'otp_code': otpCode}));
    return _decode(res);
  }

  static Future<Map<String, dynamic>> logout() async {
    final res = await http.post(Uri.parse('$baseUrl/api/v1/auth/logout'));
    return _decode(res);
  }

  static Future<Map<String, dynamic>> startBot({required String symbol, required double amount, required int maxTrades, String timeframe = 'M1', required bool useAnalysis, required String manualDirection, required int minConfidence, required int analysisSeconds}) async {
    final res = await http.post(Uri.parse('$baseUrl/api/v1/bot/start'), headers: {'Content-Type': 'application/json'}, body: jsonEncode({'symbol': symbol, 'timeframe': timeframe, 'investment_amount': amount, 'max_trades': maxTrades, 'enabled': true, 'use_analysis': useAnalysis, 'manual_direction': manualDirection, 'min_confidence': minConfidence, 'analysis_seconds': analysisSeconds}));
    return _decode(res);
  }

  static Future<Map<String, dynamic>> stopBot() async {
    final res = await http.post(Uri.parse('$baseUrl/api/v1/bot/stop'));
    return _decode(res);
  }

  static Future<Map<String, dynamic>> assets() async {
    final res = await http.get(Uri.parse('$baseUrl/api/v1/assets'));
    return _decode(res);
  }

  static Future<Map<String, dynamic>> session() async {
    final res = await http.get(Uri.parse('$baseUrl/api/v1/auth/session'));
    return _decode(res);
  }

  static Map<String, dynamic> _decode(http.Response res) {
    if (res.statusCode < 200 || res.statusCode >= 300) throw Exception('HTTP ${res.statusCode}: ${res.body}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }
}
