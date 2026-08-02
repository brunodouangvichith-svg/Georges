import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/chat_repository.dart';
import '../../data/decisions_repository.dart';
import '../../data/invalidate_all.dart';
import '../../data/agents_repository.dart';
import '../../data/prices_refresh_repository.dart';
import '../../data/securities_repository.dart';
import '../../models/decision.dart';
import '../../models/security.dart';
import '../../shared/widgets/empty_state.dart';
import '../../shared/widgets/response_dialog.dart';
import '../decision_detail/decision_detail_screen.dart';
import 'widgets/agent_activity_card.dart';
import 'widgets/macro_tile.dart';

const _filters = ['Tous', 'Achat', 'Surveiller', 'Alléger'];

/// Liste des titres suivis (CAC 40 & CAC Mid 60), filtrable par type de
/// décision, avec accès au détail (graphique + explication) par tap sur une
/// ligne, plus les actions globales de web/src/views/Univers.jsx : chat,
/// activité des agents, tuile macro (fictive), rafraîchissement des prix et
/// collecte macro. Distingue "API injoignable" de "liste vide".
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
      loadingText: "Téléchargement des prix en cours (jusqu'à une minute pour tout l'univers)…",
      action: () async {
        final result = await ref.read(pricesRefreshRepositoryProvider).refresh();
        invalidateAllData(ref);
        final failedText = result.failedSymbols.isEmpty ? '' : ' Échecs : ${result.failedSymbols.join(", ")}.';
        return '${result.updatedCount}/${result.total} titres mis à jour.$failedText';
      },
    );
  }

  void _triggerMacroCollection() {
    showResponseDialog(
      context,
      title: 'Collecte macro',
      loadingText: 'Interrogation de FRED et de la BCE en cours…',
      action: () async {
        final result = await ref.read(agentsRepositoryProvider).collect('donnees_macro');
        ref.invalidate(agentActivityProvider);
        return '${result.validated.length} validée(s), ${result.quarantinedCount} en quarantaine.';
      },
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
    final decisionsAsync = ref.watch(decisionsProvider(const DecisionsFilter()));
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
          IconButton(
            tooltip: 'Collecte macro',
            icon: const Icon(Icons.public),
            onPressed: _triggerMacroCollection,
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: _filters
                    .map((f) => Padding(
                          padding: const EdgeInsets.only(right: 6),
                          child: ChoiceChip(
                            label: Text(f),
                            selected: filter == f,
                            onSelected: (_) => setState(() => _filter = f),
                          ),
                        ))
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
                MacroTile(),
                SizedBox(width: 8),
                AgentActivityCard(),
              ],
            ),
          ),
          const SizedBox(height: 4),
          Expanded(
            child: RefreshIndicator(
              onRefresh: () => ref.refresh(securitiesProvider(null).future),
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
                  final filtered = filter == 'Tous'
                      ? page.items
                      : page.items.where((s) => decisionsMap[s.symbol]?.decisionType == filter).toList();
                  return ListView.separated(
                    itemCount: filtered.length,
                    separatorBuilder: (context, index) => const Divider(height: 1),
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
                    child: TextField(
                      controller: _chatController,
                      decoration: const InputDecoration(
                        hintText: 'Poser une question à George…',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                      onSubmitted: (_) => _askChat(),
                    ),
                  ),
                  IconButton(icon: const Icon(Icons.send), onPressed: _askChat),
                ],
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
          builder: (context) => DecisionDetailScreen(security: security, decision: decision),
        ),
      ),
    );
  }
}
