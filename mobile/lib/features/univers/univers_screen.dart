import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/chat_repository.dart';
import '../../data/decisions_repository.dart';
import '../../data/invalidate_all.dart';
import '../../data/jane_repository.dart';
import '../../data/prices_refresh_repository.dart';
import '../../data/securities_repository.dart';
import '../../models/decision.dart';
import '../../models/security.dart';
import '../../shared/widgets/empty_state.dart';
import '../../shared/widgets/response_dialog.dart';
import '../decision_detail/decision_detail_screen.dart';
import 'widgets/ask_jane_sheet.dart';
import 'widgets/breaking_news_tile.dart';
import 'widgets/energy_market_tile.dart';

const _filters = ['Tous', 'Achat', 'Surveiller', 'Alléger'];

/// Liste des titres suivis (CAC 40 & CAC Mid 60), filtrable par type de
/// décision, avec accès au détail (graphique + explication) par tap sur une
/// ligne, plus le chat et le rafraîchissement des prix. Le bouton "Collecte
/// macro" (déclenchement manuel de FRED/BCE) a été retiré ici à la demande
/// directe de l'utilisateur — `POST /agents/collect` reste appelable via
/// l'API/curl (et depuis `web/`, qui garde son propre bouton), simplement
/// plus depuis cet écran mobile. Distingue "API injoignable" de "liste vide".
class UniversScreen extends ConsumerStatefulWidget {
  const UniversScreen({super.key});

  @override
  ConsumerState<UniversScreen> createState() => _UniversScreenState();
}

class _UniversScreenState extends ConsumerState<UniversScreen> {
  // Filtre local à l'écran, purement UI — pas besoin d'un provider Riverpod
  // pour ça (contrairement aux données serveur ci-dessous).
  String _filter = 'Tous';
  final _chatController = TextEditingController();

  @override
  void dispose() {
    _chatController.dispose();
    super.dispose();
  }

  void _refreshPrices() {
    showResponseDialog(
      context,
      title: 'Mise à jour des prix',
      loadingText:
          "Téléchargement des prix en cours (jusqu'à quelques minutes pour tout l'univers, 10 ans d'historique par titre — exécuté en tâche de fond côté serveur, cet écran patiente le temps qu'il faut)…",
      action: () async {
        final result = await ref
            .read(pricesRefreshRepositoryProvider)
            .refresh();
        if (result.isFailed) {
          throw Exception(
            result.error ?? 'Échec du rafraîchissement des prix.',
          );
        }
        invalidateAllData(ref);
        final failedSymbols = result.failedSymbols ?? const [];
        final failedText = failedSymbols.isEmpty
            ? ''
            : ' Échecs : ${failedSymbols.join(", ")}.';
        return '${result.updatedCount}/${result.total} titres mis à jour.$failedText';
      },
    );
  }

  void _askJane() {
    showModalBottomSheet(
      context: context,
      isScrollControlled:
          true, // remonte au-dessus du clavier — voir ask_jane_sheet.dart
      builder: (_) => AskJaneSheet(
        onAsk: (question) => showResponseDialog(
          context,
          title: '🧠 Ask Jane',
          loadingText: 'Jane consulte sa base de connaissances méthodologique…',
          shareable: false,
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

  @override
  Widget build(BuildContext context) {
    final securitiesAsync = ref.watch(securitiesProvider(null));
    final decisionsAsync = ref.watch(
      decisionsProvider(const DecisionsFilter()),
    );
    final filter = _filter;

    // Décisions triées par date décroissante côté API : la première
    // rencontrée par titre est donc la plus récente (voir Univers.jsx).
    final decisionsMap = <String, Decision>{};
    for (final decision in decisionsAsync.value?.items ?? const <Decision>[]) {
      decisionsMap.putIfAbsent(decision.symbol, () => decision);
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Univers suivi'),
        actions: [
          IconButton(
            tooltip: 'Mise à jour des prix',
            icon: const Icon(Icons.refresh),
            onPressed: _refreshPrices,
          ),
        ],
      ),
      body: Stack(
        children: [
          Column(
            children: [
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 8,
                ),
                child: SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: _filters
                        .map(
                          (f) => Padding(
                            padding: const EdgeInsets.only(right: 6),
                            child: ChoiceChip(
                              label: Text(f),
                              selected: filter == f,
                              onSelected: (_) => setState(() => _filter = f),
                            ),
                          ),
                        )
                        .toList(),
                  ),
                ),
              ),
              SizedBox(
                height: 140,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  children: const [
                    EnergyMarketTile(),
                    SizedBox(width: 8),
                    BreakingNewsTile(),
                  ],
                ),
              ),
              const SizedBox(height: 4),
              Expanded(
                child: RefreshIndicator(
                  onRefresh: () => ref.refresh(securitiesProvider(null).future),
                  child: securitiesAsync.when(
                    loading: () =>
                        const Center(child: CircularProgressIndicator()),
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
                              message:
                                  'Aucun titre en base. Lancez '
                                  'python -m ingestion.seed puis python -m ingestion.ohlcv.',
                            ),
                          ],
                        );
                      }
                      final filtered = filter == 'Tous'
                          ? page.items
                          : page.items
                                .where(
                                  (s) =>
                                      decisionsMap[s.symbol]?.decisionType ==
                                      filter,
                                )
                                .toList();
                      return ListView.separated(
                        itemCount: filtered.length,
                        separatorBuilder: (context, index) =>
                            const Divider(height: 1),
                        itemBuilder: (context, index) {
                          final security = filtered[index];
                          return _SecurityRow(
                            security: security,
                            decision: decisionsMap[security.symbol],
                          );
                        },
                      );
                    },
                  ),
                ),
              ),
              SafeArea(
                top: false,
                child: Padding(
                  padding: const EdgeInsets.all(8),
                  child: Row(
                    children: [
                      Expanded(
                        child: ValueListenableBuilder<TextEditingValue>(
                          valueListenable: _chatController,
                          builder: (context, value, _) => TextField(
                            controller: _chatController,
                            style: TextStyle(color: Colors.blue.shade900),
                            decoration: InputDecoration(
                              hintText:
                                  'Les opportunités actuellement proposées par George',
                              border: const OutlineInputBorder(),
                              filled: true,
                              fillColor: Colors.lightBlue.shade50,
                              isDense: true,
                              suffixIcon: value.text.isEmpty
                                  ? null
                                  : IconButton(
                                      icon: const Icon(Icons.close, size: 18),
                                      tooltip: 'Effacer',
                                      onPressed: _chatController.clear,
                                    ),
                            ),
                            onSubmitted: (_) => _askChat(),
                          ),
                        ),
                      ),
                      const SizedBox(width: 4),
                      IconButton(
                        icon: const Icon(Icons.send),
                        onPressed: _askChat,
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
          // Bouton flottant "Ask Jane" — centré verticalement sur le bord
          // droit de l'écran (ni un FloatingActionButton standard, dont les
          // positions prédéfinies sont toutes bas-ancrées, ni superposé au
          // chat de George en pied d'écran).
          Positioned(
            top: 0,
            bottom: 0,
            right: 16,
            child: Center(
              child: FloatingActionButton.large(
                heroTag: 'ask_jane_fab',
                tooltip: 'Analyse Technique - Ask Jane',
                backgroundColor: Colors.lightGreen.shade100,
                onPressed: _askJane,
                child: const Text('🧠', style: TextStyle(fontSize: 48)),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SecurityRow extends StatelessWidget {
  const _SecurityRow({required this.security, required this.decision});

  final Security security;
  final Decision? decision;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      title: Text('${security.symbol} — ${security.name}'),
      subtitle: Text(security.sector),
      trailing: decision != null ? Text(decision!.decisionType) : null,
      onTap: () => Navigator.of(context).push(
        MaterialPageRoute(
          builder: (context) =>
              DecisionDetailScreen(security: security, decision: decision),
        ),
      ),
    );
  }
}
