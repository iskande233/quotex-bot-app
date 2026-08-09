import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/api_service.dart';
import '../widgets/pro_widgets.dart';

class LoginScreen extends StatefulWidget {
  final void Function(String mode) onSuccess;
  const LoginScreen({super.key, required this.onSuccess});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final emailCtrl = TextEditingController();
  final passCtrl = TextEditingController();
  final otpCtrl = TextEditingController();
  final serverCtrl = TextEditingController(text: ApiService.baseUrl);
  final otpFocus = FocusNode();
  String accountType = 'demo';
  bool loading = false;
  bool rememberEmail = true;
  String message = '';
  bool otpRequired = false;

  @override
  void initState() {
    super.initState();
    _loadRememberedEmail();
  }

  Future<void> _loadRememberedEmail() async {
    final prefs = await SharedPreferences.getInstance();
    emailCtrl.text = prefs.getString('remember_email') ?? '';
    rememberEmail = prefs.getBool('remember_email_enabled') ?? true;
    setState(() {});
  }

  @override
  void dispose() {
    emailCtrl.dispose(); passCtrl.dispose(); otpCtrl.dispose(); serverCtrl.dispose(); otpFocus.dispose(); super.dispose();
  }

  Future<void> _login() async {
    setState(() { loading = true; message = 'Connecting...'; });
    try {
      await ApiService.setBaseUrl(serverCtrl.text);
      final prefs = await SharedPreferences.getInstance();
      if (rememberEmail) {
        await prefs.setString('remember_email', emailCtrl.text.trim());
        await prefs.setBool('remember_email_enabled', true);
      } else {
        await prefs.remove('remember_email');
        await prefs.setBool('remember_email_enabled', false);
      }
      final res = await ApiService.login(email: emailCtrl.text.trim(), password: passCtrl.text, accountType: accountType, otpCode: otpCtrl.text.trim());
      widget.onSuccess((res['mode'] ?? accountType).toString().toUpperCase());
    } catch (e) {
      final text = e.toString();
      otpRequired = text.contains('OTP_REQUIRED') || text.toLowerCase().contains('verification');
      setState(() { message = otpRequired ? 'تم إرسال/طلب كود التحقق. ألصق الكود في خانة OTP واضغط LOGIN مرة أخرى.' : 'Login failed: $e'; });
      if (otpRequired) Future.delayed(const Duration(milliseconds: 250), () => otpFocus.requestFocus());
    } finally {
      if (mounted) setState(() { loading = false; });
    }
  }

  Future<void> _paper() async {
    await ApiService.logout();
    widget.onSuccess('PAPER');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF030712), Color(0xFF071027), Color(0xFF111827)]),
        ),
        child: SafeArea(
          child: ListView(padding: const EdgeInsets.all(18), children: [
            const SizedBox(height: 12),
            ProCard(border: gold.withOpacity(.45), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: const [
              Text('LATCHI BOT PRO', style: TextStyle(color: gold, fontSize: 25, fontWeight: FontWeight.w900)),
              SizedBox(height: 6),
              Text('Quotex M1 Pro Engine • Demo recommended', style: TextStyle(color: cyan, fontSize: 12)),
            ])),
            const SizedBox(height: 16),
            ProCard(child: Column(children: [
              TextField(controller: serverCtrl, decoration: proInput('Backend URL / Render URL', icon: Icons.cloud)),
              const SizedBox(height: 12),
              TextField(controller: emailCtrl, keyboardType: TextInputType.emailAddress, decoration: proInput('Quotex Email', icon: Icons.email)),
              const SizedBox(height: 12),
              TextField(controller: passCtrl, obscureText: true, decoration: proInput('Quotex Password', icon: Icons.lock)),
              const SizedBox(height: 12),
              TextField(controller: otpCtrl, focusNode: otpFocus, keyboardType: TextInputType.number, decoration: proInput(otpRequired ? 'OTP Code مطلوب' : 'OTP / Verification code (optional)', icon: Icons.verified)),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                value: accountType,
                decoration: proInput('Account Type'),
                items: const [DropdownMenuItem(value: 'demo', child: Text('Demo Account')), DropdownMenuItem(value: 'real', child: Text('Real Account'))],
                onChanged: (v) => setState(() => accountType = v ?? 'demo'),
              ),
              SwitchListTile(
                value: rememberEmail,
                contentPadding: EdgeInsets.zero,
                title: const Text('Remember Email'),
                subtitle: const Text('يحفظ الإيميل فقط ولا يحفظ كلمة السر'),
                onChanged: (v) => setState(() => rememberEmail = v),
              ),
              const SizedBox(height: 8),
              ElevatedButton.icon(onPressed: loading ? null : _login, icon: const Icon(Icons.login), label: Text(otpRequired ? 'LOGIN WITH OTP' : 'LOGIN')),
              const SizedBox(height: 10),
              OutlinedButton.icon(onPressed: loading ? null : _paper, icon: const Icon(Icons.science), label: const Text('Use Paper Mode')),
              if (message.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 14), child: Text(message, style: TextStyle(color: otpRequired ? green : gold))),
            ])),
          ]),
        ),
      ),
    );
  }
}
