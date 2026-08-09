import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/api_service.dart';
import 'login_screen.dart';
import 'dashboard_screen.dart';

class RootScreen extends StatefulWidget {
  const RootScreen({super.key});
  @override
  State<RootScreen> createState() => _RootScreenState();
}

class _RootScreenState extends State<RootScreen> {
  bool loading = true;
  bool loggedIn = false;
  String mode = 'DEMO';

  @override
  void initState() {
    super.initState();
    _restoreSession();
  }

  Future<void> _restoreSession() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final session = await ApiService.session();
      final connected = session['connected'] == true;
      final serverPersistent = session['server_persistent'] == true;
      final serverMode = (session['mode'] ?? '').toString().toUpperCase();
      if (connected && serverPersistent && serverMode != 'UNKNOWN' && serverMode != 'PAPER') {
        setState(() { mode = serverMode; loggedIn = true; loading = false; });
        return;
      }
      if (prefs.getBool('remember_login_enabled') == true) {
        final email = prefs.getString('q_email') ?? '';
        final password = prefs.getString('q_password') ?? '';
        final account = prefs.getString('q_account_type') ?? 'demo';
        if (email.isNotEmpty && password.isNotEmpty) {
          final res = await ApiService.login(email: email, password: password, accountType: account);
          setState(() { mode = (res['mode'] ?? account).toString().toUpperCase(); loggedIn = true; loading = false; });
          return;
        }
      }
    } catch (_) {}
    if (mounted) setState(() => loading = false);
  }

  @override
  Widget build(BuildContext context) {
    if (loading) return const Scaffold(body: Center(child: CircularProgressIndicator()));
    return loggedIn
        ? DashboardScreen(mode: mode, onLogout: () => setState(() { loggedIn = false; mode = 'DEMO'; }))
        : LoginScreen(onSuccess: (m) => setState(() { loggedIn = true; mode = m; }));
  }
}
