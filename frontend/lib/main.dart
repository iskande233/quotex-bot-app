import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'services/api_service.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await ApiService.init();
  runApp(const QuotexBotApp());
}

class QuotexBotApp extends StatelessWidget {
  const QuotexBotApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'LATCHI QUOTEX BOT',
      theme: ThemeData.dark(useMaterial3: true).copyWith(
        scaffoldBackgroundColor: const Color(0xFF050817),
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.amber, brightness: Brightness.dark),
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            backgroundColor: const Color(0xFFFFD700),
            foregroundColor: const Color(0xFF0A0F2C),
            textStyle: const TextStyle(fontWeight: FontWeight.w900),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
            padding: const EdgeInsets.symmetric(vertical: 14),
          ),
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF0B1024),
          foregroundColor: Colors.white,
          titleTextStyle: TextStyle(fontSize: 20, fontWeight: FontWeight.w900, color: Colors.white),
        ),
      ),
      home: const RootScreen(),
    );
  }
}

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
        ? BotDashboard(mode: mode, onLogout: () => setState(() { loggedIn = false; mode = 'DEMO'; }))
        : LoginScreen(onSuccess: (m) => setState(() { loggedIn = true; mode = m; }));
  }
}

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
  String accountType = 'demo';
  bool loading = false;
  String message = '';

  @override
  void dispose() { emailCtrl.dispose(); passCtrl.dispose(); otpCtrl.dispose(); serverCtrl.dispose(); super.dispose(); }

  Future<void> _login() async {
    setState(() { loading = true; message = 'Connecting...'; });
    try {
      await ApiService.setBaseUrl(serverCtrl.text);
      final res = await ApiService.login(email: emailCtrl.text.trim(), password: passCtrl.text, accountType: accountType, otpCode: otpCtrl.text.trim());
      widget.onSuccess((res['mode'] ?? accountType).toString().toUpperCase());
    } catch (e) {
      setState(() { message = 'Login failed: $e\nIf OTP_REQUIRED appears, enter the verification code and press Login again.'; });
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
      appBar: AppBar(title: const Text('Quotex Login')),
      body: ListView(padding: const EdgeInsets.all(18), children: [
        _hero('LATCHI QUOTEX BOT', 'Login to Quotex Demo/Real, then run a simple M1 bot.'),
        const SizedBox(height: 18),
        _field(serverCtrl, 'Backend URL / Render URL', icon: Icons.cloud),
        _field(emailCtrl, 'Quotex Email', icon: Icons.email),
        _field(passCtrl, 'Quotex Password', icon: Icons.lock, password: true),
        _field(otpCtrl, 'OTP / Verification code (optional)', icon: Icons.verified),
        const SizedBox(height: 8),
        DropdownButtonFormField<String>(
          value: accountType,
          decoration: const InputDecoration(labelText: 'Account Type'),
          items: const [
            DropdownMenuItem(value: 'demo', child: Text('Demo Account')),
            DropdownMenuItem(value: 'real', child: Text('Real Account')),
          ],
          onChanged: (v) => setState(() => accountType = v ?? 'demo'),
        ),
        const SizedBox(height: 22),
        ElevatedButton.icon(onPressed: loading ? null : _login, icon: const Icon(Icons.login), label: const Text('LOGIN')),
        const SizedBox(height: 10),
        OutlinedButton.icon(onPressed: loading ? null : _paper, icon: const Icon(Icons.science), label: const Text('Use Paper Mode')),
        if (message.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 18), child: Text(message, style: const TextStyle(color: Colors.amber))),
      ]),
    );
  }
}

class BotDashboard extends StatefulWidget {
  final String mode;
  final VoidCallback onLogout;
  const BotDashboard({super.key, required this.mode, required this.onLogout});
  @override
  State<BotDashboard> createState() => _BotDashboardState();
}

class _BotDashboardState extends State<BotDashboard> {
  final amountCtrl = TextEditingController(text: '1');
  final maxTradesCtrl = TextEditingController(text: '10');
  WebSocketChannel? channel;
  StreamSubscription? sub;
  bool running = false;
  double balance = 0, pnl = 0, price = 0;
  String mode = 'DEMO';
  String selectedAsset = 'AUTO_OTC';
  bool useAnalysis = true;
  String manualDirection = 'CALL';
  int minConfidence = 80;
  int analysisSeconds = 20;
  List<String> assets = ['AUTO_OTC'];
  List<dynamic> history = [];
  Map<String, dynamic>? latestTrade;
  String status = 'Ready';
  final Set<String> notified = {};

  @override
  void initState() { super.initState(); mode = widget.mode; _connect(); _loadAssets(); }
  @override
  void dispose() { sub?.cancel(); channel?.sink.close(); amountCtrl.dispose(); maxTradesCtrl.dispose(); super.dispose(); }

  Future<void> _loadAssets() async {
    try {
      final res = await ApiService.assets();
      final otc = ((res['otc'] as List?) ?? []).map((e) => e.toString()).toList();
      final all = ((res['assets'] as List?) ?? []).map((e) => e.toString()).toList();
      setState(() { assets = ['AUTO_OTC', ...otc, ...all.where((a) => !otc.contains(a))].toSet().toList(); });
    } catch (_) {}
  }

  void _connect() {
    sub?.cancel(); channel?.sink.close();
    channel = ApiService.connectWs();
    sub = channel!.stream.listen((event) {
      final data = jsonDecode(event as String) as Map<String, dynamic>;
      final bal = data['balance'] as Map<String, dynamic>? ?? {};
      final st = data['status'] as Map<String, dynamic>? ?? {};
      final trade = data['trade'] as Map<String, dynamic>?;
      setState(() {
        final analysis = st['last_analysis'] as Map<String, dynamic>?;
        balance = (bal['balance'] as num?)?.toDouble() ?? balance;
        pnl = (bal['session_pnl'] as num?)?.toDouble() ?? pnl;
        mode = bal['mode']?.toString() ?? mode;
        running = st['running'] == true;
        final cfg = st['config'] as Map<String, dynamic>?;
        if (cfg != null) {
          useAnalysis = cfg['use_analysis'] == true;
          manualDirection = (cfg['manual_direction'] ?? manualDirection).toString();
          minConfidence = (cfg['min_confidence'] as num?)?.toInt() ?? minConfidence;
          analysisSeconds = (cfg['analysis_seconds'] as num?)?.toInt() ?? analysisSeconds;
        }
        price = (data['price'] as num?)?.toDouble() ?? price;
        history = (data['history'] as List?) ?? history;
        if (trade != null) latestTrade = trade;
        final liveTime = DateTime.now().toIso8601String().substring(11, 19);
        if (analysis != null && analysis.isNotEmpty) {
          final aStatus = analysis['status']?.toString() ?? '';
          final msg = analysis['message']?.toString() ?? '';
          final sym = analysis['symbol']?.toString() ?? '';
          final dir = analysis['direction']?.toString() ?? '';
          final res = analysis['result']?.toString() ?? '';
          status = [aStatus, sym, dir, res, msg].where((e) => e.isNotEmpty).join(' • ');
          if (status.isEmpty) status = 'Live $liveTime';
        } else {
          status = 'Live $liveTime';
        }
      });
      if (trade != null) _notify(data['type']?.toString() ?? 'snapshot', trade);
    }, onError: (e) => setState(() => status = 'Connection error'), onDone: () => setState(() => status = 'Disconnected'));
  }

  void _notify(String type, Map<String, dynamic> t) {
    final id = t['id']?.toString() ?? '';
    if (id.isEmpty || !notified.add('$type$id')) return;
    if (type == 'trade_opened') _snack('تم دخول الصفقة', '${t['symbol']} ${t['direction']} @ ${t['entry_price']}', Colors.amber);
    if (type == 'trade_result') {
      final r = t['result']?.toString() ?? 'PENDING';
      _snack('نتيجة الصفقة: $r', '${t['symbol']} | PnL: ${t['pnl']}', r == 'WIN' ? Colors.greenAccent : Colors.redAccent);
    }
  }

  void _snack(String title, String msg, Color c) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(backgroundColor: const Color(0xFF111A35), content: Row(children: [Icon(Icons.notifications_active, color: c), const SizedBox(width: 10), Expanded(child: Text('$title\n$msg'))])));
  }

  Future<void> _start() async {
    try {
      await ApiService.startBot(symbol: selectedAsset, amount: double.tryParse(amountCtrl.text) ?? 1, maxTrades: int.tryParse(maxTradesCtrl.text) ?? 10, useAnalysis: useAnalysis, manualDirection: manualDirection, minConfidence: minConfidence, analysisSeconds: analysisSeconds);
      setState(() => status = 'Bot started');
    } catch (e) { setState(() => status = 'Start failed: $e'); }
  }

  Future<void> _stop() async { await ApiService.stopBot(); setState(() => status = 'Stopped'); }
  Future<void> _logout() async { await ApiService.logout(); widget.onLogout(); }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('LATCHI BOT'), actions: [
        IconButton(onPressed: _logout, icon: const Icon(Icons.logout)),
        IconButton(onPressed: () { _connect(); _loadAssets(); }, icon: const Icon(Icons.refresh)),
      ]),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        _accountCard(),
        const SizedBox(height: 12),
        _controls(),
        const SizedBox(height: 12),
        _signalCard(),
        const SizedBox(height: 12),
        _history(),
      ]),
    );
  }

  Widget _accountCard() => _panel('Live Account', 'Mode: $mode\nBalance: ${balance.toStringAsFixed(2)}\nSession PnL: ${pnl.toStringAsFixed(2)}\nPrice: ${price.toStringAsFixed(6)}\nMode: ${useAnalysis ? 'Analysis ${minConfidence == 80 ? '80-90%' : minConfidence == 90 ? '90-95%' : '95%'}' : 'Direct $manualDirection'}\n$status');

  Widget _controls() => Container(
    padding: const EdgeInsets.all(14), decoration: _box(), child: Column(children: [
      DropdownButtonFormField<String>(value: assets.contains(selectedAsset) ? selectedAsset : 'AUTO_OTC', decoration: const InputDecoration(labelText: 'زوج التداول'), items: assets.map((a) => DropdownMenuItem(value: a, child: Text(a == 'AUTO_OTC' ? 'Auto OTC' : a))).toList(), onChanged: (v) => setState(() => selectedAsset = v ?? 'AUTO_OTC')),
      const SizedBox(height: 8),
      SwitchListTile(
        value: useAnalysis,
        contentPadding: EdgeInsets.zero,
        title: const Text('تشغيل بالتحليل القوي'),
        subtitle: Text(useAnalysis ? 'يفحص الأزواج حتى $analysisSeconds ثانية ويختار صفقة ضمن نطاق ${minConfidence == 80 ? '80-90%' : minConfidence == 90 ? '90-95%' : '95%'}' : 'تشغيل مباشر بدون تحليل بالاتجاه المختار'),
        onChanged: (v) => setState(() => useAnalysis = v),
      ),
      if (!useAnalysis) DropdownButtonFormField<String>(value: manualDirection, decoration: const InputDecoration(labelText: 'الاتجاه بدون تحليل'), items: const [DropdownMenuItem(value: 'CALL', child: Text('CALL شراء')), DropdownMenuItem(value: 'PUT', child: Text('PUT بيع'))], onChanged: (v) => setState(() => manualDirection = v ?? 'CALL')),
      if (useAnalysis) Row(children: [Expanded(child: DropdownButtonFormField<int>(value: minConfidence, decoration: const InputDecoration(labelText: 'نطاق قوة الإشارة'), items: const [DropdownMenuItem(value: 80, child: Text('80% - 90%')), DropdownMenuItem(value: 90, child: Text('90% - 95%')), DropdownMenuItem(value: 95, child: Text('95%'))], onChanged: (v) => setState(() => minConfidence = v ?? 80))), const SizedBox(width: 12), Expanded(child: DropdownButtonFormField<int>(value: analysisSeconds, decoration: const InputDecoration(labelText: 'مدة التحليل'), items: const [DropdownMenuItem(value: 20, child: Text('20s')), DropdownMenuItem(value: 30, child: Text('30s')), DropdownMenuItem(value: 45, child: Text('45s'))], onChanged: (v) => setState(() => analysisSeconds = v ?? 20)))]),
      Row(children: [Expanded(child: TextField(controller: amountCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'المبلغ'))), const SizedBox(width: 12), Expanded(child: TextField(controller: maxTradesCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Max')))]),
      const SizedBox(height: 14),
      Row(children: [Expanded(child: ElevatedButton.icon(onPressed: running ? null : _start, icon: const Icon(Icons.play_arrow), label: const Text('START'))), const SizedBox(width: 10), Expanded(child: ElevatedButton.icon(onPressed: running ? _stop : null, icon: const Icon(Icons.stop), label: const Text('STOP')))]),
    ]));

  Widget _signalCard() {
    final t = latestTrade;
    if (t == null) return _panel('Signal', useAnalysis ? 'سيتم تحليل الأزواج واختيار أفضل صفقة.\nالحالة: $status' : 'سيتم الدخول مباشرة بدون تحليل.\nالحالة: $status');
    final result = t['result']?.toString() ?? 'PENDING';
    final dir = t['direction']?.toString() ?? '';
    return Container(padding: const EdgeInsets.all(18), decoration: _box(stroke: result == 'WIN' ? Colors.greenAccent : result == 'LOSS' ? Colors.redAccent : Colors.amber), child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      const Text('💲 صفقة جديدة 💲', textAlign: TextAlign.center, style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900, color: Colors.amber)),
      const Divider(color: Colors.white38),
      Text('📊 الزوج: ${t['symbol']}'),
      const Text('⏱️ المدة: M1'),
      Text('💰 المبلغ: ${t['amount']}'),
      Text(dir == 'CALL' ? '📈 الاتجاه: CALL 🔼 (شراء)' : '📉 الاتجاه: PUT 🔻 (بيع)'),
      const Divider(color: Colors.white38),
      Text(result == 'PENDING' ? '⏳ النتيجة: قيد الانتظار' : (result == 'WIN' ? '🟢💰 ربح مباشر WIN ✅' : '💔 خسارة LOSS ❌'), textAlign: TextAlign.center, style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: result == 'WIN' ? Colors.greenAccent : result == 'LOSS' ? Colors.redAccent : Colors.amber)),
    ]));
  }

  Widget _history() => Container(padding: const EdgeInsets.all(14), decoration: _box(), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    const Text('Trade History', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.amber)),
    if (history.isEmpty) const Padding(padding: EdgeInsets.all(12), child: Text('No trades yet')),
    ...history.take(12).map((e) { final m = e as Map<String, dynamic>; final r = m['result']?.toString() ?? 'PENDING'; return ListTile(dense: true, title: Text('${m['symbol']} ${m['direction']}'), subtitle: Text('Entry ${m['entry_price']} | Exit ${m['exit_price']}'), trailing: Text(r, style: TextStyle(color: r == 'WIN' ? Colors.greenAccent : r == 'LOSS' ? Colors.redAccent : Colors.amber, fontWeight: FontWeight.bold))); }),
  ]));
}

Widget _hero(String title, String subtitle) => Container(padding: const EdgeInsets.all(18), decoration: _box(), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(title, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w900, color: Colors.amber)), const SizedBox(height: 6), Text(subtitle)]));
Widget _field(TextEditingController c, String label, {IconData? icon, bool password = false}) => Padding(padding: const EdgeInsets.only(bottom: 12), child: TextField(controller: c, obscureText: password, decoration: InputDecoration(labelText: label, prefixIcon: icon == null ? null : Icon(icon))));
Widget _panel(String title, String body) => Container(padding: const EdgeInsets.all(16), decoration: _box(), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.amber)), const SizedBox(height: 8), Text(body)]));
BoxDecoration _box({Color stroke = Colors.amber}) => BoxDecoration(gradient: const LinearGradient(colors: [Color(0xFF101936), Color(0xFF0B1228)]), borderRadius: BorderRadius.circular(22), border: Border.all(color: stroke.withOpacity(.65)), boxShadow: [BoxShadow(color: Colors.black.withOpacity(.25), blurRadius: 14, offset: const Offset(0, 8))]);
