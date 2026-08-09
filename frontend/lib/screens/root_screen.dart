import 'package:flutter/material.dart';
import 'login_screen.dart';
import 'dashboard_screen.dart';

class RootScreen extends StatefulWidget {
  const RootScreen({super.key});
  @override
  State<RootScreen> createState() => _RootScreenState();
}

class _RootScreenState extends State<RootScreen> {
  bool loggedIn = false;
  String mode = 'DEMO';

  @override
  Widget build(BuildContext context) {
    return loggedIn
        ? DashboardScreen(mode: mode, onLogout: () => setState(() { loggedIn = false; mode = 'DEMO'; }))
        : LoginScreen(onSuccess: (m) => setState(() { loggedIn = true; mode = m; }));
  }
}
