import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../services/api_service.dart';
import '../widgets/pro_widgets.dart';

class DashboardScreen extends StatefulWidget {
  final String mode;
  final VoidCallback onLogout;
  const DashboardScreen({super.key, required this.mode, required this.onLogout});
  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final amountCtrl = TextEditingController(text: '1');
  final maxTradesCtrl = TextEditingController(text: '5');
  WebSocketChannel? channel;
  StreamSubscription? sub;
  bool running = false;
  double balance = 0, pnl = 0, price = 0;
  String mode = 'DEMO';
  String selectedAsset = 'AUTO_OTC';
  bool useAnalysis = true;
  String manualDirection = 'CALL';
  int minConfidence = 90;
  int analysisSeconds = 45;
  double takeProfit = 6.0;
  double stopLoss = 3.0;
  int maxConsecutiveLosses = 2;
  int cooldownAfterLoss = 15;
  int pairCooldown = 5;
  String strategyMode = 'normal';
  int autoBlacklistLosses = 3;
  List<String> assets = ['AUTO_OTC'];
  List<dynamic> history = [];
  List<dynamic> logs = [];
  Map<String, dynamic> stats = {};
  Map<String, dynamic>? latestTrade;
  Map<String, dynamic>? currentSignal;
  String status = 'Ready';
  final Set<String> notified = {};
  Timer? countdownTimer;
  int nowSec = DateTime.now().millisecondsSinceEpoch ~/ 1000;
  bool applyingSettings = false;

  @override
  void initState() {
    super.initState();
    mode = widget.mode;
    _loadSavedSettings();
    _connect();
    _loadAssets();
    countdownTimer = Timer.periodic(const Duration(seconds: 1), (_) => setState(() => nowSec = DateTime.now().millisecondsSinceEpoch ~/ 1000));
  }

  @override
  void dispose() {
    countdownTimer?.cancel(); sub?.cancel(); channel?.sink.close(); amountCtrl.dispose(); maxTradesCtrl.dispose(); super.dispose();
  }

  Future<void> _loadSavedSettings() async {
    final p = await SharedPreferences.getInstance();
    amountCtrl.text = p.getString('amount') ?? amountCtrl.text;
    maxTradesCtrl.text = p.getString('max_trades') ?? maxTradesCtrl.text;
    takeProfit = p.getDouble('take_profit') ?? takeProfit;
    stopLoss = p.getDouble('stop_loss') ?? stopLoss;
    maxConsecutiveLosses = p.getInt('max_consecutive_losses') ?? maxConsecutiveLosses;
    cooldownAfterLoss = p.getInt('cooldown_after_loss') ?? cooldownAfterLoss;
    pairCooldown = p.getInt('pair_cooldown') ?? pairCooldown;
    useAnalysis = p.getBool('use_analysis') ?? useAnalysis;
    minConfidence = p.getInt('min_confidence') ?? minConfidence;
    analysisSeconds = p.getInt('analysis_seconds') ?? analysisSeconds;
    manualDirection = p.getString('manual_direction') ?? manualDirection;
    selectedAsset = p.getString('selected_asset') ?? selectedAsset;
    strategyMode = p.getString('strategy_mode') ?? strategyMode;
    autoBlacklistLosses = p.getInt('auto_blacklist_losses') ?? autoBlacklistLosses;
    if (mounted) setState(() {});
  }

  Future<void> _saveSettings() async {
    final p = await SharedPreferences.getInstance();
    await p.setString('amount', amountCtrl.text);
    await p.setString('max_trades', maxTradesCtrl.text);
    await p.setDouble('take_profit', takeProfit);
    await p.setDouble('stop_loss', stopLoss);
    await p.setInt('max_consecutive_losses', maxConsecutiveLosses);
    await p.setInt('cooldown_after_loss', cooldownAfterLoss);
    await p.setInt('pair_cooldown', pairCooldown);
    await p.setBool('use_analysis', useAnalysis);
    await p.setInt('min_confidence', minConfidence);
    await p.setInt('analysis_seconds', analysisSeconds);
    await p.setString('manual_direction', manualDirection);
    await p.setString('selected_asset', selectedAsset);
    await p.setString('strategy_mode', strategyMode);
    await p.setInt('auto_blacklist_losses', autoBlacklistLosses);
  }

  Future<void> _loadAssets() async {
    try {
      final res = await ApiService.assets();
      final otc = ((res['otc'] as List?) ?? []).map((e) => e.toString()).toList();
      final all = ((res['assets'] as List?) ?? []).map((e) => e.toString()).toList();
      setState(() => assets = ['AUTO_OTC', ...otc, ...all.where((a) => !otc.contains(a))].toSet().toList());
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
      final signal = st['current_signal'] as Map<String, dynamic>?;
      setState(() {
        final analysis = st['last_analysis'] as Map<String, dynamic>?;
        balance = (bal['balance'] as num?)?.toDouble() ?? balance;
        pnl = (bal['session_pnl'] as num?)?.toDouble() ?? pnl;
        mode = bal['mode']?.toString() ?? mode;
        final serverRunning = st['running'] == true;
        running = serverRunning;
        final cfg = st['config'] as Map<String, dynamic>?;
        // Do not overwrite local saved settings with backend defaults while the bot is stopped.
        // This was the reason settings appeared to reset and the analysis switch turned itself back on.
        if (cfg != null && serverRunning && !applyingSettings) {
          useAnalysis = cfg['use_analysis'] == true;
          manualDirection = (cfg['manual_direction'] ?? manualDirection).toString();
          minConfidence = (cfg['min_confidence'] as num?)?.toInt() ?? minConfidence;
          analysisSeconds = (cfg['analysis_seconds'] as num?)?.toInt() ?? analysisSeconds;
          takeProfit = (cfg['take_profit'] as num?)?.toDouble() ?? takeProfit;
          stopLoss = (cfg['stop_loss'] as num?)?.toDouble() ?? stopLoss;
          maxConsecutiveLosses = (cfg['max_consecutive_losses'] as num?)?.toInt() ?? maxConsecutiveLosses;
          cooldownAfterLoss = (cfg['cooldown_after_loss_minutes'] as num?)?.toInt() ?? cooldownAfterLoss;
          pairCooldown = (cfg['pair_cooldown_minutes'] as num?)?.toInt() ?? pairCooldown;
          strategyMode = (cfg['strategy_mode'] ?? strategyMode).toString();
          autoBlacklistLosses = (cfg['auto_blacklist_losses'] as num?)?.toInt() ?? autoBlacklistLosses;
        }
        price = (data['price'] as num?)?.toDouble() ?? price;
        history = (data['history'] as List?) ?? history;
        logs = (st['logs'] as List?) ?? logs;
        stats = (st['stats'] as Map<String, dynamic>?) ?? stats;
        currentSignal = signal;
        if (trade != null) latestTrade = trade;
        if (analysis != null && analysis.isNotEmpty) {
          status = [analysis['status'], analysis['symbol'], analysis['direction'], analysis['result'], analysis['message']].where((e) => e != null && e.toString().isNotEmpty).join(' • ');
        } else {
          status = 'Live ${DateTime.now().toIso8601String().substring(11, 19)}';
        }
      });
      if (trade != null) _notify(data['type']?.toString() ?? 'snapshot', trade);
    }, onError: (_) => setState(() => status = 'Connection error'), onDone: () => setState(() => status = 'Disconnected'));
  }

  void _notify(String type, Map<String, dynamic> t) {
    final id = t['id']?.toString() ?? '';
    if (id.isEmpty || !notified.add('$type$id')) return;
    if (type == 'trade_opened') _snack('تم دخول الصفقة', '${t['symbol']} ${t['direction']} @ ${t['entry_price']}', gold);
    if (type == 'trade_result') {
      final r = t['result']?.toString() ?? 'PENDING';
      _snack('نتيجة الصفقة: $r', '${t['symbol']} | PnL: ${t['pnl']}', r == 'WIN' ? green : red);
    }
  }

  void _snack(String title, String msg, Color c) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(backgroundColor: const Color(0xFF111827), content: Row(children: [Icon(Icons.notifications_active, color: c), const SizedBox(width: 10), Expanded(child: Text('$title\n$msg'))])));
  }

  Future<void> _applyServerConfig({bool showSnack = false}) async {
    applyingSettings = true;
    try {
      final amount = double.tryParse(amountCtrl.text) ?? 1;
      final maxTrades = int.tryParse(maxTradesCtrl.text) ?? 5;
      if (running) {
        await ApiService.updateBotConfig(
          symbol: selectedAsset,
          amount: amount,
          maxTrades: maxTrades,
          useAnalysis: useAnalysis,
          manualDirection: manualDirection,
          minConfidence: minConfidence,
          analysisSeconds: analysisSeconds,
          takeProfit: takeProfit,
          stopLoss: stopLoss,
          maxConsecutiveLosses: maxConsecutiveLosses,
          cooldownAfterLoss: cooldownAfterLoss,
          pairCooldown: pairCooldown,
          strategyMode: strategyMode,
          autoBlacklistLosses: autoBlacklistLosses,
        );
      } else {
        await ApiService.startBot(
          symbol: selectedAsset,
          amount: amount,
          maxTrades: maxTrades,
          useAnalysis: useAnalysis,
          manualDirection: manualDirection,
          minConfidence: minConfidence,
          analysisSeconds: analysisSeconds,
          takeProfit: takeProfit,
          stopLoss: stopLoss,
          maxConsecutiveLosses: maxConsecutiveLosses,
          cooldownAfterLoss: cooldownAfterLoss,
          pairCooldown: pairCooldown,
          strategyMode: strategyMode,
          autoBlacklistLosses: autoBlacklistLosses,
        );
      }
      if (showSnack) _snack('تم تطبيق الإعدادات', running ? 'تم تحديث البوت على السيرفر مباشرة' : 'تم تشغيل البوت بالإعدادات الجديدة', green);
    } finally {
      Future.delayed(const Duration(seconds: 2), () { if (mounted) applyingSettings = false; });
    }
  }

  Future<void> _start() async {
    try {
      await _saveSettings();
      await _applyServerConfig(showSnack: true);
      setState(() => status = 'Bot started with saved settings');
    } catch (e) { setState(() => status = 'Start failed: $e'); }
  }

  Future<void> _randomTradeNow() async {
    try {
      setState(() => status = 'Opening random OTC trade now...');
      final res = await ApiService.randomTrade(amount: double.tryParse(amountCtrl.text) ?? 1);
      final trade = res['trade'] as Map<String, dynamic>?;
      if (trade != null) {
        setState(() { latestTrade = trade; status = 'Random trade opened'; });
        _snack('تم دخول صفقة عشوائية', '${trade['symbol']} ${trade['direction']}', gold);
      }
    } catch (e) { setState(() => status = 'Random trade failed: $e'); }
  }

  Future<void> _stop() async { await ApiService.stopBot(); setState(() { status = 'Stopped completely'; running = false; currentSignal = null; }); }
  Future<void> _stopAfterCurrent() async { await ApiService.stopAfterCurrent(); setState(() => status = 'Will stop after current trade'); }
  Future<void> _logout() async { await ApiService.logout(); widget.onLogout(); }

  Future<void> _openLogs() async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => LogsScreen(logs: logs)));
  }

  Future<void> _openSettings() async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => BotSettingsScreen(
      serverUrl: ApiService.baseUrl,
      amount: amountCtrl.text,
      maxTrades: maxTradesCtrl.text,
      takeProfit: takeProfit,
      stopLoss: stopLoss,
      maxConsecutiveLosses: maxConsecutiveLosses,
      cooldownAfterLoss: cooldownAfterLoss,
      pairCooldown: pairCooldown,
      strategyMode: strategyMode,
      autoBlacklistLosses: autoBlacklistLosses,
      minConfidence: minConfidence,
      analysisSeconds: analysisSeconds,
      onSave: (server, amount, maxTrades, tp, sl, mcl, cal, pc, sm, abl, conf, secs) async {
        await ApiService.setBaseUrl(server);
        amountCtrl.text = amount;
        maxTradesCtrl.text = maxTrades;
        takeProfit = tp;
        stopLoss = sl;
        maxConsecutiveLosses = mcl;
        cooldownAfterLoss = cal;
        pairCooldown = pc;
        strategyMode = sm;
        autoBlacklistLosses = abl;
        minConfidence = conf;
        analysisSeconds = secs;
        await _saveSettings();
        setState(() => status = running ? 'Applying settings to running bot...' : 'Settings saved');
        if (running) await _applyServerConfig(showSnack: true);
        _connect();
      },
    )));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF030712), Color(0xFF071027), Color(0xFF111827)]),
        ),
        child: SafeArea(
          child: Column(children: [
            _header(),
            Expanded(child: ListView(padding: const EdgeInsets.all(16), children: [
              _balanceCard(), const SizedBox(height: 16), _statsCard(), const SizedBox(height: 16), _controls(), const SizedBox(height: 16), _signalCard(), const SizedBox(height: 16), _history(),
              const Padding(padding: EdgeInsets.all(12), child: Text('التداول ينطوي على مخاطر مالية. يُنصح دائماً بالربط والتجربة على حساب Demo أولاً.', textAlign: TextAlign.center, style: TextStyle(color: muted, fontSize: 10))),
            ])),
          ]),
        ),
      ),
    );
  }

  Widget _header() => Container(
    padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
    decoration: BoxDecoration(color: const Color(0xCC0F172A), border: Border(bottom: BorderSide(color: Colors.white.withOpacity(.08)))),
    child: Row(children: [
      Container(width: 38, height: 38, decoration: BoxDecoration(gradient: const LinearGradient(colors: [gold, Color(0xFFD97706)]), borderRadius: BorderRadius.circular(10)), child: const Center(child: Text('Q', style: TextStyle(color: Colors.black, fontWeight: FontWeight.w900, fontSize: 18)))),
      const SizedBox(width: 10),
      const Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('LATCHI BOT', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w900)), Text('Quotex M1 Pro Engine', style: TextStyle(color: cyan, fontSize: 10))])),
      IconButton(onPressed: _openLogs, icon: const Icon(Icons.list_alt)),
      IconButton(onPressed: _openSettings, icon: const Icon(Icons.settings)),
      IconButton(onPressed: _logout, icon: const Icon(Icons.logout)),
    ]),
  );

  Widget _balanceCard() => ProCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Row(children: [
      Container(padding: const EdgeInsets.all(3), decoration: BoxDecoration(color: Colors.black.withOpacity(.25), borderRadius: BorderRadius.circular(10)), child: Row(children: [
        StatusPill(mode, color: mode == 'REAL' ? red : green),
      ])),
      const Spacer(),
      const StatusPill('CONNECTED', color: green),
    ]),
    const SizedBox(height: 14),
    const Text('الرصيد الحالي (USD)', style: TextStyle(color: muted, fontSize: 12)),
    Text('\$${fmtMoney(balance)}', style: const TextStyle(fontSize: 30, fontWeight: FontWeight.w900)),
    const Divider(color: Color(0x22FFFFFF)),
    Row(children: [
      Expanded(child: _miniStat('Session PnL', pnl >= 0 ? '+${fmtMoney(pnl)}' : fmtMoney(pnl), pnl >= 0 ? green : red)),
      Expanded(child: _miniStat('السعر الحقيقي', price.toStringAsFixed(6), Colors.white)),
    ]),
    const SizedBox(height: 8),
    Text('TP: +${fmtMoney(takeProfit)} | SL: -${fmtMoney(stopLoss)} | Max Loss: $maxConsecutiveLosses | Cooldown: ${cooldownAfterLoss}m', style: const TextStyle(color: muted, fontSize: 11)),
    const SizedBox(height: 4),
    Text(status, style: const TextStyle(color: gold, fontSize: 12)),
  ]));

  Widget _miniStat(String t, String v, Color c) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(t, style: const TextStyle(color: muted, fontSize: 11)), Text(v, style: TextStyle(color: c, fontWeight: FontWeight.w800))]);

  Widget _statsCard() => ProCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    const SectionTitle('إحصائيات الجلسة', trailing: Text('SESSION', style: TextStyle(color: gold, fontSize: 11))),
    const SizedBox(height: 10),
    Row(children: [
      Expanded(child: _miniStat('Trades', '${stats['total'] ?? 0}', Colors.white)),
      Expanded(child: _miniStat('Wins', '${stats['wins'] ?? 0}', green)),
      Expanded(child: _miniStat('Losses', '${stats['losses'] ?? 0}', red)),
    ]),
    const SizedBox(height: 10),
    Row(children: [
      Expanded(child: _miniStat('Accuracy', '${stats['accuracy'] ?? 0}%', gold)),
      Expanded(child: _miniStat('PnL', '${stats['session_pnl'] ?? 0}', (stats['session_pnl'] ?? 0) is num && (stats['session_pnl'] as num) < 0 ? red : green)),
      Expanded(child: _miniStat('Loss Streak', '${stats['consecutive_losses'] ?? 0}', red)),
    ]),
  ]));

  Widget _controls() => ProCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    const SectionTitle('إعدادات البوت والتحليل', trailing: Text('PRO', style: TextStyle(color: gold, fontSize: 11))),
    const SizedBox(height: 12),
    DropdownButtonFormField<String>(value: assets.contains(selectedAsset) ? selectedAsset : 'AUTO_OTC', decoration: proInput('زوج التداول'), items: assets.map((a) => DropdownMenuItem(value: a, child: Text(a == 'AUTO_OTC' ? 'Auto OTC (المرشح الأقوى)' : a))).toList(), onChanged: (v) => setState(() => selectedAsset = v ?? 'AUTO_OTC')),
    const SizedBox(height: 10),
    SwitchListTile(value: useAnalysis, contentPadding: EdgeInsets.zero, title: const Text('التحليل الذكي المتقدم'), subtitle: Text(useAnalysis ? 'يفحص كل أزواج OTC بسرعة ويختار أفضل فرصة تلقائياً' : 'تشغيل مباشر بدون تحليل بالاتجاه المختار'), onChanged: (v) async { setState(() => useAnalysis = v); await _saveSettings(); if (running) await _applyServerConfig(showSnack: true); }),
    if (!useAnalysis) DropdownButtonFormField<String>(value: manualDirection, decoration: proInput('الاتجاه بدون تحليل'), items: const [DropdownMenuItem(value: 'CALL', child: Text('CALL شراء')), DropdownMenuItem(value: 'PUT', child: Text('PUT بيع'))], onChanged: (v) => setState(() => manualDirection = v ?? 'CALL')),
    Row(children: [Expanded(child: TextField(controller: amountCtrl, keyboardType: TextInputType.number, decoration: proInput('مبلغ الصفقة'))), const SizedBox(width: 10), Expanded(child: TextField(controller: maxTradesCtrl, keyboardType: TextInputType.number, decoration: proInput('Max Trades')))]),
    const SizedBox(height: 12),
    Row(children: [Expanded(child: ElevatedButton.icon(onPressed: running ? null : _start, icon: const Icon(Icons.play_arrow), label: const Text('START BOT'))), const SizedBox(width: 10), Expanded(child: OutlinedButton.icon(onPressed: running ? _stop : null, icon: const Icon(Icons.stop), label: const Text('STOP')))]),
    const SizedBox(height: 10),
    OutlinedButton.icon(onPressed: running ? _stopAfterCurrent : null, icon: const Icon(Icons.pause_circle), label: const Text('إيقاف بعد الصفقة الحالية')),
    const SizedBox(height: 10),
    OutlinedButton.icon(onPressed: running ? _stop : null, icon: const Icon(Icons.power_settings_new, color: red), label: const Text('إيقاف فوري كامل للبوت')),
    const SizedBox(height: 10),
    OutlinedButton.icon(onPressed: _randomTradeNow, icon: const Icon(Icons.casino), label: const Text('صفقة عشوائية للتجربة الفورية')),
  ]));


  Widget _signalCard() {
    final t = latestTrade;
    final sig = currentSignal;
    final pendingTrade = t != null && (t['result']?.toString() ?? 'PENDING') == 'PENDING';
    if (sig != null && sig['status'] == 'SCHEDULED' && !pendingTrade) return _scheduledSignal(sig);
    if (t == null) return ProCard(border: gold.withOpacity(.8), child: Text(useAnalysis ? 'سيتم تحليل الأزواج واختيار أفضل صفقة.\nالحالة: $status' : 'سيتم الدخول مباشرة بدون تحليل.\nالحالة: $status'));
    return _tradeSignal(t);
  }

  Widget _scheduledSignal(Map<String, dynamic> sig) {
    final dir = sig['direction']?.toString() ?? '';
    final entry = sig['entry_time'];
    final entrySec = entry == null ? 0 : (entry as num).toInt();
    final execute = sig['execute_time'];
    final resultCheck = sig['result_check_time'];
    final executeSec = execute == null ? 0 : (execute as num).toInt();
    final resultSec = resultCheck == null ? 0 : (resultCheck as num).toInt();
    final left = entrySec > 0 ? (entrySec - nowSec).clamp(0, 999) : 0;
    final execLeft = executeSec > 0 ? (executeSec - nowSec).clamp(0, 999) : 0;
    final resultLeft = resultSec > 0 ? (resultSec - nowSec).clamp(0, 999) : 0;
    return ProCard(border: gold, child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      const Text('⚡ الإشارة الحالية', style: TextStyle(color: gold, fontWeight: FontWeight.w900, fontSize: 16)),
      LinearProgressIndicator(value: left == 0 ? 1 : (60 - left.clamp(0, 60)) / 60, color: gold, backgroundColor: Colors.white10),
      const SizedBox(height: 12),
      _dataGrid({'الزوج': '${sig['symbol']}', 'المدة': 'M1', 'الدخول الرسمي بعد': '${left}s', 'إرسال الأمر بعد': '${execLeft}s', 'القوة': '${sig['confidence']}%', 'الاتجاه': dir == 'CALL' ? 'CALL 🔼' : 'PUT 🔻'}),
    ]));
  }

  Widget _tradeSignal(Map<String, dynamic> t) {
    final result = t['result']?.toString() ?? 'PENDING';
    final dir = t['direction']?.toString() ?? '';
    final rct = t['result_check_time'];
    final resultLeft = rct == null ? 0 : (((rct as num).toDouble()).toInt() - nowSec).clamp(0, 999);
    return ProCard(border: result == 'WIN' ? green : result == 'LOSS' ? red : gold, child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      const Text('💲 صفقة جديدة 💲', textAlign: TextAlign.center, style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900, color: gold)),
      const Divider(color: Colors.white38),
      _dataGrid({'الزوج': '${t['symbol']}', 'المدة': 'M1', 'المبلغ': '${t['amount']}', 'الاتجاه': dir == 'CALL' ? 'CALL 🔼 شراء' : 'PUT 🔻 بيع'}),
      const Divider(color: Colors.white38),
      Text(result == 'PENDING' ? '⏳ النتيجة: قيد الانتظار • بعد ${resultLeft}s' : (result == 'WIN' ? '🟢💰 ربح مباشر WIN ✅' : '💔 خسارة LOSS ❌'), textAlign: TextAlign.center, style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: result == 'WIN' ? green : result == 'LOSS' ? red : gold)),
    ]));
  }

  Widget _dataGrid(Map<String, String> data) => Wrap(spacing: 8, runSpacing: 8, children: data.entries.map((e) => Container(width: 150, padding: const EdgeInsets.all(9), decoration: BoxDecoration(color: Colors.black.withOpacity(.18), borderRadius: BorderRadius.circular(10)), child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [Text(e.key, style: const TextStyle(color: muted, fontSize: 12)), Flexible(child: Text(e.value, textAlign: TextAlign.end, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 12)))]))).toList());

  Widget _history() => ProCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    const SectionTitle('سجل الصفقات', trailing: Text('آخر صفقات البوت', style: TextStyle(color: muted, fontSize: 11))),
    const SizedBox(height: 8),
    if (history.isEmpty) const Padding(padding: EdgeInsets.all(12), child: Text('No trades yet')),
    ...history.take(12).map((e) { final m = e as Map<String, dynamic>; final r = m['result']?.toString() ?? 'PENDING'; return ListTile(dense: true, title: Text('${m['symbol']} ${m['direction']}'), subtitle: Text('In: ${m['entry_price']} | Out: ${m['exit_price']}'), trailing: StatusPill(r, color: r == 'WIN' ? green : r == 'LOSS' ? red : gold)); }),
  ]));
}

class LogsScreen extends StatelessWidget {
  final List<dynamic> logs;
  const LogsScreen({super.key, required this.logs});

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Bot Logs')),
    body: ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: logs.isEmpty ? 1 : logs.length,
      itemBuilder: (_, i) {
        if (logs.isEmpty) return const ProCard(child: Text('No logs yet'));
        final l = logs[i] as Map<String, dynamic>;
        final ts = l['time'] == null
            ? ''
            : DateTime.fromMillisecondsSinceEpoch(((l['time'] as num).toDouble() * 1000).toInt())
                .toIso8601String()
                .substring(11, 19);
        return Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: ProCard(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${l['event']}  •  $ts', style: const TextStyle(color: gold, fontWeight: FontWeight.bold)),
              const SizedBox(height: 6),
              Text('${l['message']}'),
            ]),
          ),
        );
      },
    ),
  );
}

class BotSettingsScreen extends StatefulWidget {
  final String serverUrl, amount, maxTrades;
  final double takeProfit, stopLoss;
  final int maxConsecutiveLosses, cooldownAfterLoss, pairCooldown, autoBlacklistLosses, minConfidence, analysisSeconds;
  final String strategyMode;
  final Future<void> Function(
    String server,
    String amount,
    String maxTrades,
    double takeProfit,
    double stopLoss,
    int maxConsecutiveLosses,
    int cooldownAfterLoss,
    int pairCooldown,
    String strategyMode,
    int autoBlacklistLosses,
    int minConfidence,
    int analysisSeconds,
  ) onSave;

  const BotSettingsScreen({
    super.key,
    required this.serverUrl,
    required this.amount,
    required this.maxTrades,
    required this.takeProfit,
    required this.stopLoss,
    required this.maxConsecutiveLosses,
    required this.cooldownAfterLoss,
    required this.pairCooldown,
    required this.strategyMode,
    required this.autoBlacklistLosses,
    required this.minConfidence,
    required this.analysisSeconds,
    required this.onSave,
  });

  @override
  State<BotSettingsScreen> createState() => _BotSettingsScreenState();
}

class _BotSettingsScreenState extends State<BotSettingsScreen> {
  late final serverCtrl = TextEditingController(text: widget.serverUrl);
  late final amountCtrl = TextEditingController(text: widget.amount);
  late final maxTradesCtrl = TextEditingController(text: widget.maxTrades);
  late final takeProfitCtrl = TextEditingController(text: widget.takeProfit.toStringAsFixed(0));
  late final stopLossCtrl = TextEditingController(text: widget.stopLoss.toStringAsFixed(0));
  late int maxLosses = widget.maxConsecutiveLosses;
  late int cooldownLoss = widget.cooldownAfterLoss;
  late int pairCd = widget.pairCooldown;
  late String strat = widget.strategyMode;
  late int autoBl = widget.autoBlacklistLosses;
  late int conf = widget.minConfidence;
  late int secs = widget.analysisSeconds;
  String message = '';

  @override
  void dispose() {
    serverCtrl.dispose();
    amountCtrl.dispose();
    maxTradesCtrl.dispose();
    takeProfitCtrl.dispose();
    stopLossCtrl.dispose();
    super.dispose();
  }

  Future<void> _testConnection() async {
    try {
      final r = await ApiService.testConnection();
      setState(() => message = 'Backend OK: ${r['name'] ?? r['ok']}');
    } catch (e) {
      setState(() => message = 'Backend failed: $e');
    }
  }

  Future<void> _testTelegram() async {
    try {
      await ApiService.testTelegram();
      setState(() => message = 'Telegram test sent');
    } catch (e) {
      setState(() => message = 'Telegram failed: $e');
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Settings')),
    body: ListView(padding: const EdgeInsets.all(16), children: [
      ProCard(child: Column(children: [
        TextField(controller: serverCtrl, decoration: proInput('Backend URL')),
        const SizedBox(height: 10),
        Row(children: [
          Expanded(child: OutlinedButton.icon(onPressed: _testConnection, icon: const Icon(Icons.cloud_done), label: const Text('Test Backend'))),
          const SizedBox(width: 10),
          Expanded(child: OutlinedButton.icon(onPressed: _testTelegram, icon: const Icon(Icons.send), label: const Text('Test Telegram'))),
        ]),
      ])),
      const SizedBox(height: 14),
      ProCard(child: Column(children: [
        const SectionTitle('Trading Defaults'),
        const SizedBox(height: 10),
        Row(children: [
          Expanded(child: TextField(controller: amountCtrl, keyboardType: TextInputType.number, decoration: proInput('Default Amount'))),
          const SizedBox(width: 10),
          Expanded(child: TextField(controller: maxTradesCtrl, keyboardType: TextInputType.number, decoration: proInput('Max Trades'))),
        ]),
        const SizedBox(height: 10),
        Row(children: [
          Expanded(child: TextField(controller: takeProfitCtrl, keyboardType: TextInputType.number, decoration: proInput('Take Profit +\$'))),
          const SizedBox(width: 10),
          Expanded(child: TextField(controller: stopLossCtrl, keyboardType: TextInputType.number, decoration: proInput('Stop Loss -\$'))),
        ]),
        const SizedBox(height: 10),
        DropdownButtonFormField<int>(
          value: maxLosses,
          decoration: proInput('Max Consecutive Losses'),
          items: const [1, 2, 3, 4, 5].map((v) => DropdownMenuItem(value: v, child: Text('$v'))).toList(),
          onChanged: (v) => setState(() => maxLosses = v ?? 3),
        ),
        const SizedBox(height: 10),
        Row(children: [
          Expanded(child: DropdownButtonFormField<int>(
            value: cooldownLoss,
            decoration: proInput('Cooldown After Loss'),
            items: const [0, 2, 5, 10, 15].map((v) => DropdownMenuItem(value: v, child: Text('${v}m'))).toList(),
            onChanged: (v) => setState(() => cooldownLoss = v ?? 2),
          )),
          const SizedBox(width: 10),
          Expanded(child: DropdownButtonFormField<int>(
            value: pairCd,
            decoration: proInput('Pair Cooldown'),
            items: const [0, 3, 5, 10].map((v) => DropdownMenuItem(value: v, child: Text('${v}m'))).toList(),
            onChanged: (v) => setState(() => pairCd = v ?? 5),
          )),
        ]),
        const SizedBox(height: 10),
        DropdownButtonFormField<String>(value: strat, decoration: proInput('Strategy Mode'), items: const [DropdownMenuItem(value: 'safe', child: Text('Safe')), DropdownMenuItem(value: 'normal', child: Text('Normal')), DropdownMenuItem(value: 'aggressive', child: Text('Aggressive'))], onChanged: (v) => setState(() => strat = v ?? 'normal')),
        const SizedBox(height: 10),
        Row(children: [
          Expanded(child: DropdownButtonFormField<int>(value: conf, decoration: proInput('Signal Strength'), items: const [0, 50, 60, 70, 80, 85, 90, 95].map((v) => DropdownMenuItem(value: v, child: Text('$v%'))).toList(), onChanged: (v) => setState(() => conf = v ?? 90))),
          const SizedBox(width: 10),
          Expanded(child: DropdownButtonFormField<int>(value: secs, decoration: proInput('Analysis Duration'), items: const [5, 10, 20, 30, 45, 55, 60].map((v) => DropdownMenuItem(value: v, child: Text('${v}s'))).toList(), onChanged: (v) => setState(() => secs = v ?? 45))),
        ]),
        const SizedBox(height: 10),
        DropdownButtonFormField<int>(value: autoBl, decoration: proInput('Auto Blacklist Losses'), items: const [DropdownMenuItem(value: 2, child: Text('2')), DropdownMenuItem(value: 3, child: Text('3')), DropdownMenuItem(value: 4, child: Text('4')), DropdownMenuItem(value: 5, child: Text('5'))], onChanged: (v) => setState(() => autoBl = v ?? 3)),
        const SizedBox(height: 14),
        ElevatedButton.icon(
          onPressed: () async {
            await widget.onSave(
              serverCtrl.text,
              amountCtrl.text,
              maxTradesCtrl.text,
              double.tryParse(takeProfitCtrl.text) ?? 6,
              double.tryParse(stopLossCtrl.text) ?? 3,
              maxLosses,
              cooldownLoss,
              pairCd,
              strat,
              autoBl,
              conf,
              secs,
            );
            if (context.mounted) Navigator.pop(context);
          },
          icon: const Icon(Icons.save),
          label: const Text('Save Settings'),
        ),
      ])),
      if (message.isNotEmpty) Padding(padding: const EdgeInsets.all(12), child: Text(message, style: const TextStyle(color: gold))),
    ]),
  );
}
