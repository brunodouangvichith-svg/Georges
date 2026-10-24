import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_theme.dart';
import '../../data/chat_repository.dart';
import '../../data/decisions_repository.dart';
import '../../data/invalidate_all.dart';
import '../../data/jane_repository.dart';
import '../../data/patterns_repository.dart';
import '../../data/prices_refresh_repository.dart';
import '../../data/prices_repository.dart';
import '../../data/securities_repository.dart';
import '../../models/decision.dart';
import '../../models/pattern.dart';
import '../../models/security.dart';
import '../../shared/widgets/empty_state.dart';
import '../../shared/widgets/response_dialog.dart';
import '../decision_detail/decision_detail_screen.dart';
import 'widgets/ask_jane_sheet.dart';
import 'widgets/breaking_news_tile.dart';
import 'widgets/candlestick_chart.dart';
import 'widgets/energy_market_tile.dart';
import 'widgets/univers_radar.dart';
import 'widgets/univers_radar_layout.dart';

const _filters = ['Tous', 'Achat', 'Surveiller', 'Alléger'];

/// Écran Univers — même structure que `web/src/views/Univers.jsx` (demande
/// directe de l'utilisateur) : en-tête « George / Univers » avec compteurs,
/// radar de l'univers, valeur sélectionnée (graphique, figure, décision,
/// niveaux), raisonnement de George, puis la watchlist filtrable, l'énergie
/// et l'actualité, et la barre de question en pied d'écran. Tout vient de
/// l'API, aucun chiffre de démonstration.
///
/// Différences assumées avec le web, faute de place ou parce que l'action
/// n'existe pas vraiment : pas de boutons « Valider les niveaux » /
/// « Ajuster » (sur le web ils n'enregistrent rien ; la vraie confirmation
/// est dans l'onglet Trading) — à la place, « Voir le détail » ouvre la fiche
/// complète (graphique 10 ans, indicateurs, fondamentaux) ; pas de journal
/// des sous-agents ni de George Index ; pas de « Collecte macro » (retiré du
/// mobile à la demande de l'utilisateur, toujours sur le web).
///
/// Les figures de tout l'univers arrivent en UNE requête
/// (`latestPatternsProvider`) : un appel par titre saturait le pool de
/// connexions de l'API.
class UniversScreen extends ConsumerStatefulWidget {
  const UniversScreen({super.key});

  @override
  ConsumerState<UniversScreen> createState() => _UniversScreenState();
}

class _UniversScreenState extends ConsumerState<UniversScreen> {
  String _filter = 'Tous';
  String? _selected;
  final _chatController = TextEditingController();
  final _scrollController = ScrollController();

  @override
  void dispose() {
    _chatController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _refreshPrices() {
    showResponseDialog(
      context,
      title: 'Mise à jour des prix',
      loadingText:
          "Téléchargement des prix en cours (jusqu'à quelques minutes pour tout l'univers, 10 ans d'historique par titre — exécuté en tâche de fond côté serveur, cet écran patiente le temps qu'il faut)…",
      action: () async {
        final result = await ref.read(pricesRefreshRepositoryProvider).refresh();
        if (result.isFailed) {
          throw Exception(result.error ?? 'Échec du rafraîchissement des prix.');
        }
        invalidateAllData(ref);
        final failedSymbols = result.failedSymbols ?? const [];
        final failedText = failedSymbols.isEmpty ? '' : ' Échecs : ${failedSymbols.join(", ")}.';
        return '${result.updatedCount}/${result.total} titres mis à jour.$failedText';
      },
    );
  }

  void _askJane() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true, // remonte au-dessus du clavier — voir ask_jane_sheet.dart
      builder: (_) => AskJaneSheet(
        onAsk: (question) => showResponseDialog(
          context,
          title: '🧠 Ask Jane',
          loadingText: 'Jane consulte sa base de connaissances méthodologique…',
          action: () async {
            final answer = await ref.read(janeRepositoryProvider).ask(question);
            return 'Question : $question\n\n$answer';
          },
        ),
      ),
    );
  }

  void _askChat() {
    final question = _chatController.text.trim();
    if (question.isEmpty) return;
    _chatController.clear();
    showResponseDialog(
      context,
      title: 'George répond',
      loadingText: 'George réfléchit…',
      action: () => ref.read(chatRepositoryProvider).ask(question),
    );
  }

  void _select(String symbol, {bool scrollToTop = false}) {
    setState(() => _selected = symbol);
    if (scrollToTop && _scrollController.hasClients) {
      _scrollController.animateTo(0, duration: const Duration(milliseconds: 350), curve: Curves.easeOut);
    }
  }

  @override
  Widget build(BuildContext context) {
    final securitiesAsync = ref.watch(securitiesProvider(null));
    final decisionsAsync = ref.watch(decisionsProvider(const DecisionsFilter()));
    final patterns = ref.watch(latestPatternsProvider).value ?? const <String, Pattern>{};

    // Décisions triées par date décroissante côté API : la première
    // rencontrée par titre est donc la plus récente (voir Univers.jsx).
    final decisionsMap = <String, Decision>{};
    for (final decision in decisionsAsync.value?.items ?? const <Decision>[]) {
      decisionsMap.putIfAbsent(decision.symbol, () => decision);
    }

    return Scaffold(
      body: Stack(
        children: [
          Column(
            children: [
              Expanded(
                child: RefreshIndicator(
                  onRefresh: () {
                    ref.invalidate(latestPatternsProvider);
                    ref.invalidate(decisionsProvider);
                    return ref.refresh(securitiesProvider(null).future);
                  },
                  child: securitiesAsync.when(
                    loading: () => const Center(child: CircularProgressIndicator()),
                    error: (error, stack) => ListView(
                      children: const [
                        EmptyState(
                          message:
                              "Impossible de contacter l'API — si le service vient d'être "
                              'inactif, le premier appel peut prendre jusqu\'à ~50s '
                              '(réveil du plan gratuit Render), sinon vérifiez la connexion.',
                        ),
                      ],
                    ),
                    data: (page) {
                      if (page.items.isEmpty) {
                        return ListView(
                          children: const [
                            EmptyState(
                              message: 'Aucun titre en base. Lancez '
                                  'python -m ingestion.seed puis python -m ingestion.ohlcv.',
                            ),
                          ],
                        );
                      }
                      return _buildContent(page.items, decisionsMap, patterns);
                    },
                  ),
                ),
              ),
              _AskDock(controller: _chatController, onSubmit: _askChat),
            ],
          ),
          // Bouton flottant "Ask Jane" — centré verticalement sur le bord
          // droit (placement demandé par l'utilisateur).
          Positioned(
            top: 0,
            bottom: 0,
            right: 16,
            child: Center(
              // Réduit de 15 % à la demande de l'utilisateur (le radar est
              // dessous) : même bouton, mis à l'échelle — la zone de tap suit.
              child: Transform.scale(
                scale: 0.85,
                child: FloatingActionButton.large(
                  heroTag: 'ask_jane_fab',
                  tooltip: 'Analyse Technique - Ask Jane',
                  backgroundColor: Colors.lightGreen.shade100,
                  onPressed: _askJane,
                  child: const Text('🧠', style: TextStyle(fontSize: 48)),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildContent(List<Security> securities, Map<String, Decision> decisionsMap, Map<String, Pattern> patterns) {
    final selectedSymbol = (_selected != null && securities.any((s) => s.symbol == _selected))
        ? _selected!
        : securities.first.symbol;
    final selectedSecurity = securities.firstWhere((s) => s.symbol == selectedSymbol);
    final selectedDecision = decisionsMap[selectedSymbol];
    final selectedPattern = patterns[selectedSymbol];
    final pricesAsync = ref.watch(securityPricesProvider(selectedSymbol));
    final closes = pricesAsync.value?.items.map((bar) => bar.close).toList() ?? const <double>[];

    var achat = 0, surveiller = 0, alleger = 0, active = 0;
    for (final s in securities) {
      if (patterns.containsKey(s.symbol)) active++;
      final d = decisionsMap[s.symbol]?.decisionType;
      if (d == null) continue;
      if (isBullishDecision(d)) {
        achat++;
      } else if (d == 'Surveiller') {
        surveiller++;
      } else {
        alleger++;
      }
    }
    final size = securities.length;
    final layout = buildRadarLayout(securities, patterns, decisionsMap);
    final filtered = _filter == 'Tous'
        ? securities
        : securities.where((s) => decisionsMap[s.symbol]?.decisionType == _filter).toList();

    return ListView(
      controller: _scrollController,
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 16),
      children: [
        Text('George / Univers', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontSize: 20)),
        const SizedBox(height: 2),
        const _Label('CAC 40 & CAC Mid 60 → décisions expliquées'),
        const SizedBox(height: 12),
        LayoutBuilder(
          builder: (context, constraints) {
            final w = (constraints.maxWidth - 2 * 14) / 3;
            return Wrap(
              spacing: 14,
              runSpacing: 12,
              children: [
                _Counter(width: w, label: 'Valeurs', value: '$size', ratio: 1),
                _Counter(width: w, label: 'Figures actives', value: '$active', ratio: active / size),
                _Counter(width: w, label: 'Achat', value: '$achat', ratio: achat / size, color: AppColors.positive),
                _Counter(
                    width: w, label: 'Surveiller', value: '$surveiller', ratio: surveiller / size, color: AppColors.warning),
                _Counter(width: w, label: 'Alléger', value: '$alleger', ratio: alleger / size, color: AppColors.negative),
              ],
            );
          },
        ),
        const SizedBox(height: 10),
        const Divider(),
        Row(
          children: [
            Expanded(child: Text('$size valeurs suivies', style: const TextStyle(fontSize: 12, color: AppColors.textDim))),
            OutlinedButton(onPressed: _refreshPrices, child: const Text('Mise à jour des prix')),
          ],
        ),
        const SizedBox(height: 4),
        UniversRadar(layout: layout, selectedSymbol: selectedSymbol, onSelect: _select, closes: closes),
        const SizedBox(height: 8),
        _Panel(
          title: 'Valeur sélectionnée',
          children: [
            Text(selectedSecurity.name, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            Text('${selectedSecurity.symbol} · ${selectedSecurity.sector}',
                style: const TextStyle(fontSize: 12, color: AppColors.textDim)),
            const SizedBox(height: 10),
            Container(
              color: AppColors.panelAlt,
              height: 170,
              alignment: Alignment.center,
              child: pricesAsync.when(
                loading: () => const Text("Chargement de l'historique…", style: TextStyle(color: AppColors.textDim)),
                error: (error, stack) => const Padding(
                  padding: EdgeInsets.all(12),
                  child: Text(
                    "Historique indisponible — le serveur met parfois 1-2 minutes à répondre après une pause (plan gratuit).",
                    textAlign: TextAlign.center,
                    style: TextStyle(color: AppColors.textDim, fontSize: 12),
                  ),
                ),
                data: (pricesPage) => pricesPage.items.isEmpty
                    ? const Text('Aucun historique de prix pour ce titre.', style: TextStyle(color: AppColors.textDim))
                    : LayoutBuilder(
                        builder: (context, constraints) => CandlestickChart(
                          candles: pricesPage.items,
                          context: selectedPattern?.context,
                          indexOffset: pricesPage.total - pricesPage.items.length,
                          takeProfit: selectedDecision?.takeProfit,
                          stopLoss: selectedDecision?.stopLoss,
                          width: constraints.maxWidth,
                          height: 160,
                        ),
                      ),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              selectedPattern != null
                  ? '- - Figure détectée par George : ${selectedPattern.patternType}'
                  : 'Aucune figure active détectée pour ce titre.',
              style: const TextStyle(fontSize: 11.5, color: AppColors.textDim),
            ),
            const SizedBox(height: 8),
            _KeyValue('Pattern détecté', Text(selectedPattern?.patternType ?? '—', style: _valueStyle)),
            _KeyValue('Confiance',
                Text(selectedPattern != null ? '${selectedPattern.confidence.round()}%' : '—', style: _valueStyle)),
            _KeyValue(
              'Décision',
              selectedDecision != null ? _DecisionTag(selectedDecision.decisionType) : const Text('—', style: _valueStyle),
            ),
            if (selectedDecision != null) ...[
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(child: _LevelBox(label: 'Take-profit', value: selectedDecision.takeProfit, color: AppColors.positive)),
                  const SizedBox(width: 8),
                  Expanded(child: _LevelBox(label: 'Stop-loss', value: selectedDecision.stopLoss, color: AppColors.negative)),
                ],
              ),
            ],
            const SizedBox(height: 10),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (context) => DecisionDetailScreen(security: selectedSecurity, decision: selectedDecision),
                  ),
                ),
                child: const Text('Voir le détail (10 ans, indicateurs, fondamentaux)'),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        _Panel(
          title: 'Raisonnement / George',
          children: [
            Text(
              _reasoningLines(selectedSymbol, pricesAsync.value?.items.length ?? 0, selectedPattern, selectedDecision),
              style: monoTextStyle(fontSize: 11.5, color: AppColors.text),
            ),
            const SizedBox(height: 8),
            Text(
              selectedDecision?.rationale ??
                  (selectedDecision != null
                      ? "Aucune note courte pour cette décision — demandez l'explication complète à George."
                      : 'Aucune décision enregistrée pour ce titre — posez une question à George dans la barre en bas si vous voulez son avis.'),
              style: const TextStyle(fontSize: 12, color: AppColors.textDim, height: 1.4),
            ),
            if (selectedDecision != null) ...[
              const SizedBox(height: 8),
              OutlinedButton(
                onPressed: () => showResponseDialog(
                  context,
                  title: 'George explique — $selectedSymbol',
                  loadingText: 'George réfléchit…',
                  action: () async =>
                      (await ref.read(decisionsRepositoryProvider).explain(selectedDecision.id)).explanation,
                  symbol: selectedSymbol,
                  takeProfit: selectedDecision.takeProfit,
                  stopLoss: selectedDecision.stopLoss,
                ),
                child: const Text('Demander une analyse à George →'),
              ),
            ],
          ],
        ),
        const SizedBox(height: 12),
        _Panel(
          title: 'Watchlist / figures actives',
          children: [
            Wrap(
              spacing: 6,
              children: [
                for (final f in _filters)
                  ChoiceChip(label: Text(f), selected: _filter == f, onSelected: (_) => setState(() => _filter = f)),
              ],
            ),
            const SizedBox(height: 6),
            if (filtered.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Text('Aucune valeur pour ce filtre.', style: TextStyle(color: AppColors.textDim, fontSize: 12)),
              ),
            for (final s in filtered)
              _WatchlistRow(
                security: s,
                pattern: patterns[s.symbol],
                decision: decisionsMap[s.symbol],
                selected: s.symbol == selectedSymbol,
                onTap: () => _select(s.symbol, scrollToTop: true),
              ),
          ],
        ),
        const SizedBox(height: 12),
        SizedBox(
          height: 140,
          child: ListView(
            scrollDirection: Axis.horizontal,
            children: const [EnergyMarketTile(), SizedBox(width: 8), BreakingNewsTile()],
          ),
        ),
      ],
    );
  }
}

String _reasoningLines(String symbol, int barCount, Pattern? pattern, Decision? decision) {
  final lines = <String>[
    'serie    = prices("$symbol", $barCount)',
    'figure   = detect(serie) → ${pattern?.patternType ?? "aucune"}',
    if (pattern != null) 'conf     = ${pattern.confidence.round()} %',
    decision == null
        ? 'decision = —'
        : 'decision = ${decision.decisionType}'
            '${decision.takeProfit != null ? " · tp ${decision.takeProfit!.toStringAsFixed(2)}" : ""}'
            '${decision.stopLoss != null ? " · sl ${decision.stopLoss!.toStringAsFixed(2)}" : ""}',
  ];
  return [for (var i = 0; i < lines.length; i++) '${(31 + i).toString().padLeft(3, "0")}  ${lines[i]}'].join('\n');
}

const _valueStyle = TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppColors.text);

class _Label extends StatelessWidget {
  const _Label(this.text);

  final String text;

  @override
  Widget build(BuildContext context) => Text(
        text.toUpperCase(),
        style: const TextStyle(fontSize: 10.5, letterSpacing: 0.8, fontWeight: FontWeight.w600, color: AppColors.textDim),
      );
}

/// Compteur d'en-tête : libellé, valeur, barre fine proportionnelle à
/// `ratio` dans la couleur qui porte le sens — `web/src/components/Counter.jsx`.
class _Counter extends StatelessWidget {
  const _Counter({required this.width, required this.label, required this.value, required this.ratio, this.color = AppColors.accent});

  final double width;
  final String label;
  final String value;
  final double ratio;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label.toUpperCase(),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 10, letterSpacing: 0.6, color: AppColors.textDim)),
          const SizedBox(height: 4),
          Text(value, style: monoTextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppColors.text)),
          const SizedBox(height: 6),
          ClipRRect(
            borderRadius: BorderRadius.circular(2),
            child: LinearProgressIndicator(
              value: ratio.isNaN ? 0 : ratio.clamp(0.0, 1.0),
              minHeight: 3,
              backgroundColor: AppColors.hairline,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}

class _Panel extends StatelessWidget {
  const _Panel({required this.title, required this.children});

  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.panel,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.hairline),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [_Label(title), const SizedBox(height: 10), ...children],
      ),
    );
  }
}

class _KeyValue extends StatelessWidget {
  const _KeyValue(this.label, this.value);

  final String label;
  final Widget value;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 3),
        child: Row(
          children: [
            Expanded(child: Text(label, style: const TextStyle(fontSize: 12, color: AppColors.textDim))),
            value,
          ],
        ),
      );
}

class _DecisionTag extends StatelessWidget {
  const _DecisionTag(this.type);

  final String type;

  @override
  Widget build(BuildContext context) {
    final color = radarDecisionColor(type);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(color: color.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(4)),
      child: Text(type, style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600, color: color)),
    );
  }
}

class _LevelBox extends StatelessWidget {
  const _LevelBox({required this.label, required this.value, required this.color});

  final String label;
  final double? value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 8),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.hairline),
      ),
      child: Column(
        children: [
          _Label(label),
          const SizedBox(height: 3),
          Text(value != null ? '${value!.toStringAsFixed(2)} €' : '—',
              style: monoTextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: color)),
        ],
      ),
    );
  }
}

class _WatchlistRow extends StatelessWidget {
  const _WatchlistRow({
    required this.security,
    required this.pattern,
    required this.decision,
    required this.selected,
    required this.onTap,
  });

  final Security security;
  final Pattern? pattern;
  final Decision? decision;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = decision != null ? radarDecisionColor(decision!.decisionType) : AppColors.textDim;
    return Material(
      color: selected ? AppColors.panelAlt : Colors.transparent,
      child: InkWell(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 9, horizontal: 4),
          decoration: const BoxDecoration(border: Border(bottom: BorderSide(color: AppColors.hairline))),
          child: Row(
            children: [
              Expanded(
                flex: 5,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(security.symbol, style: monoTextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.text)),
                    Text(security.name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontSize: 12, color: AppColors.textDim)),
                  ],
                ),
              ),
              Expanded(
                flex: 4,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(pattern?.patternType ?? '—',
                        maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12)),
                    if (pattern != null) ...[
                      const SizedBox(height: 4),
                      SizedBox(
                        width: 64,
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(3),
                          child: LinearProgressIndicator(
                            value: (pattern!.confidence / 100).clamp(0.0, 1.0),
                            minHeight: 5,
                            backgroundColor: AppColors.panelAlt,
                            color: color,
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              if (decision != null) _DecisionTag(decision!.decisionType) else const Text('—', style: _valueStyle),
            ],
          ),
        ),
      ),
    );
  }
}

/// Barre de question en pied d'écran (« George explique › » sur le web).
class _AskDock extends StatelessWidget {
  const _AskDock({required this.controller, required this.onSubmit});

  final TextEditingController controller;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Container(
        padding: const EdgeInsets.fromLTRB(10, 8, 6, 8),
        decoration: const BoxDecoration(
          color: AppColors.panel,
          border: Border(top: BorderSide(color: AppColors.hairline)),
        ),
        child: Row(
          children: [
            Expanded(
              child: ValueListenableBuilder<TextEditingValue>(
                valueListenable: controller,
                builder: (context, value, _) => TextField(
                  controller: controller,
                  decoration: InputDecoration(
                    hintText: 'Poser une question à George…',
                    isDense: true,
                    suffixIcon: value.text.isEmpty
                        ? null
                        : IconButton(icon: const Icon(Icons.close, size: 18), tooltip: 'Effacer', onPressed: controller.clear),
                  ),
                  onSubmitted: (_) => onSubmit(),
                ),
              ),
            ),
            const SizedBox(width: 4),
            IconButton.filled(icon: const Icon(Icons.send), tooltip: 'Envoyer', onPressed: onSubmit),
          ],
        ),
      ),
    );
  }
}
