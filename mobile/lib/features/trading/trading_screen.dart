import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../core/theme/app_theme.dart';
import '../../data/decisions_repository.dart';
import '../../models/decision.dart';
import '../../models/performance.dart';
import '../../shared/widgets/empty_state.dart';
import '../../shared/widgets/response_dialog.dart';

/// Onglet « Trading » — miroir de web/src/views/Trading.jsx : suivi du cycle
/// de vie des décisions (proposee → confirmee → sortie_proposee → cloturee)
/// et performance réalisée (GET /decisions/performance).
///
/// Sur mobile, les 4 colonnes du web deviennent des onglets, plus un onglet
/// « Performance ». George ne passe AUCUN ordre : « Confirmer » enregistre
/// seulement une position suivie, « Confirmer la sortie » la clôture et écrit
/// son résultat dans decision_outcomes.
class TradingScreen extends ConsumerWidget {
  const TradingScreen({super.key});

  static const statuses = [
    ('proposee', 'Proposées', 'À valider ou ajuster'),
    ('confirmee', 'En position', 'Suivies par le job de surveillance'),
    ('sortie_proposee', 'Sorties', 'Take-profit ou stop-loss franchi'),
    ('cloturee', 'Clôturées', 'Historique'),
  ];

  void _runJob(BuildContext context, WidgetRef ref, {required bool propose}) {
    final repo = ref.read(decisionsRepositoryProvider);
    showResponseDialog(
      context,
      title: propose ? 'Lancer une détection' : 'Surveiller les positions',
      loadingText: propose ? 'Recherche de nouvelles opportunités…' : 'Vérification des positions en cours…',
      shareable: false,
      action: () async {
        final count = propose ? await repo.proposeNew() : await repo.monitor();
        _invalidateTrading(ref);
        if (propose) {
          return count == 0
              ? 'Aucune nouvelle proposition : aucune figure active ne dépasse le seuil de confiance.'
              : '$count nouvelle(s) proposition(s) ajoutée(s) dans « Proposées ».';
        }
        return count == 0
            ? 'Aucune position n’a franchi son take-profit ou son stop-loss.'
            : '$count sortie(s) proposée(s) — voir l’onglet « Sorties ».';
      },
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return DefaultTabController(
      length: statuses.length + 1,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Trading'),
          actions: [
            PopupMenuButton<String>(
              tooltip: 'Actions',
              onSelected: (value) => _runJob(context, ref, propose: value == 'propose'),
              itemBuilder: (context) => const [
                PopupMenuItem(value: 'propose', child: Text('Lancer une détection')),
                PopupMenuItem(value: 'monitor', child: Text('Surveiller les positions')),
              ],
            ),
          ],
          bottom: TabBar(
            isScrollable: true,
            tabAlignment: TabAlignment.start,
            tabs: [
              for (final s in statuses) _CountTab(status: s.$1, label: s.$2),
              const Tab(text: 'Performance'),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            for (final s in statuses) _StatusList(status: s.$1, hint: s.$3),
            const _PerformanceView(),
          ],
        ),
      ),
    );
  }
}

/// Invalide décisions et performance après une action du cycle de vie.
void _invalidateTrading(WidgetRef ref) {
  ref.invalidate(decisionsProvider);
  ref.invalidate(performanceProvider);
}

const _unreachable =
    "Impossible de contacter l'API — si le service vient d'être inactif, le premier appel peut prendre "
    "jusqu'à ~50s (réveil du plan gratuit Render), sinon vérifiez la connexion.";

Color decisionColor(String type) {
  if (type == 'Achat' || type == 'Renforcer') return AppColors.positive;
  if (type == 'Surveiller') return AppColors.warning;
  return AppColors.negative;
}

Color pctColor(double? value) {
  if (value == null || value == 0) return AppColors.textDim;
  return value > 0 ? AppColors.positive : AppColors.negative;
}

String formatPct(double? value, {int digits = 2}) =>
    value == null ? '—' : '${value > 0 ? '+' : ''}${value.toStringAsFixed(digits)} %';

String _money(double? v) => v == null ? '—' : '${v.toStringAsFixed(2)} €';

const _exitLabels = {'sortie_totale': 'Sortie totale', 'sortie_partielle': 'Sortie partielle'};
const _resultLabels = {'take_profit_hit': 'Take-profit touché', 'stop_loss_hit': 'Stop-loss touché'};

/// Saisie d'un niveau : vide = garder la valeur proposée ; NaN = invalide.
double? parseLevel(String text) {
  final trimmed = text.trim();
  if (trimmed.isEmpty) return null;
  final n = double.tryParse(trimmed.replaceAll(',', '.'));
  return n != null && n > 0 ? n : double.nan;
}

class _CountTab extends ConsumerWidget {
  const _CountTab({required this.status, required this.label});

  final String status;
  final String label;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final total = ref.watch(decisionsProvider(DecisionsFilter(status: status))).value?.total;
    return Tab(text: total == null ? label : '$label ($total)');
  }
}

class _StatusList extends ConsumerWidget {
  const _StatusList({required this.status, required this.hint});

  final String status;
  final String hint;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final filter = DecisionsFilter(status: status);
    final decisionsAsync = ref.watch(decisionsProvider(filter));
    // Résultat réalisé de chaque décision clôturée (performance.trades).
    final outcomes = status == 'cloturee'
        ? {for (final t in ref.watch(performanceProvider).value?.trades ?? const <TradeOutcome>[]) t.decisionId: t}
        : const <int, TradeOutcome>{};

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(performanceProvider);
        ref.invalidate(decisionsProvider(filter));
        await ref.read(decisionsProvider(filter).future);
      },
      child: decisionsAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, st) => ListView(children: const [EmptyState(message: _unreachable)]),
        data: (page) {
          if (page.items.isEmpty) {
            return ListView(children: [EmptyState(message: 'Aucune décision. $hint.')]);
          }
          return ListView.builder(
            padding: const EdgeInsets.all(12),
            itemCount: page.items.length + 1,
            itemBuilder: (context, index) {
              if (index == page.items.length) {
                return page.total > page.items.length
                    ? Padding(
                        padding: const EdgeInsets.all(8),
                        child: Text(
                          '${page.items.length} affichées sur ${page.total} (les plus récentes).',
                          style: Theme.of(context).textTheme.labelSmall,
                        ),
                      )
                    : const SizedBox.shrink();
              }
              final decision = page.items[index];
              return DecisionCard(
                key: ValueKey(decision.id),
                decision: decision,
                outcome: outcomes[decision.id],
              );
            },
          );
        },
      ),
    );
  }
}

/// Carte d'une décision, avec les actions propres à son statut.
class DecisionCard extends ConsumerStatefulWidget {
  const DecisionCard({super.key, required this.decision, this.outcome});

  final Decision decision;
  final TradeOutcome? outcome;

  @override
  ConsumerState<DecisionCard> createState() => _DecisionCardState();
}

class _DecisionCardState extends ConsumerState<DecisionCard> {
  late final TextEditingController _tp;
  late final TextEditingController _sl;
  bool _busy = false;
  String? _error;

  Decision get d => widget.decision;

  @override
  void initState() {
    super.initState();
    _tp = TextEditingController(text: d.takeProfit?.toString() ?? '');
    _sl = TextEditingController(text: d.stopLoss?.toString() ?? '');
    _tp.addListener(_onEdit);
    _sl.addListener(_onEdit);
  }

  void _onEdit() => setState(() {});

  @override
  void dispose() {
    _tp.dispose();
    _sl.dispose();
    super.dispose();
  }

  Future<void> _run(Future<void> Function() action) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await action();
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _confirm() async {
    final tp = parseLevel(_tp.text);
    final sl = parseLevel(_sl.text);
    await _run(() async {
      await ref.read(decisionsRepositoryProvider).confirm(
            d.id,
            takeProfit: tp != null && tp != d.takeProfit ? tp : null,
            stopLoss: sl != null && sl != d.stopLoss ? sl : null,
          );
      _invalidateTrading(ref);
    });
  }

  Future<void> _recompute() async {
    await _run(() async {
      final updated = await ref.read(decisionsRepositoryProvider).proposeLevels(d.id);
      if (!mounted) return;
      _tp.text = updated.takeProfit?.toString() ?? '';
      _sl.text = updated.stopLoss?.toString() ?? '';
      ref.invalidate(decisionsProvider);
    });
  }

  Future<void> _confirmExit() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Clôturer la position ?'),
        content: Text('Clôturer définitivement ${d.symbol} ? Le résultat sera enregistré, '
            'aucun ordre n’est passé chez un courtier.'),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(false), child: const Text('❌ Annuler')),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            style: FilledButton.styleFrom(backgroundColor: AppColors.negative),
            child: const Text('Oui, clôturer'),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    await _run(() async {
      await ref.read(decisionsRepositoryProvider).confirmExit(d.id);
      _invalidateTrading(ref);
    });
  }

  void _explain() {
    showResponseDialog(
      context,
      title: 'George explique — ${d.symbol}',
      loadingText: 'George réfléchit…',
      symbol: d.symbol,
      takeProfit: d.takeProfit,
      stopLoss: d.stopLoss,
      action: () async => (await ref.read(decisionsRepositoryProvider).explain(d.id)).explanation,
    );
  }

  @override
  Widget build(BuildContext context) {
    final color = decisionColor(d.decisionType);
    final dim = Theme.of(context).colorScheme.outline;
    final tpValue = parseLevel(_tp.text);
    final slValue = parseLevel(_sl.text);
    final invalid = (tpValue?.isNaN ?? false) || (slValue?.isNaN ?? false);

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Container(
        decoration: BoxDecoration(border: Border(left: BorderSide(color: color, width: 3))),
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(d.symbol, style: monoTextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                      Text(
                        'Créée le ${DateFormat('dd/MM/yyyy').format(d.createdAt)} · confiance ${d.confidence.round()} %',
                        style: TextStyle(fontSize: 11.5, color: dim),
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(d.decisionType, style: TextStyle(color: color, fontSize: 11.5, fontWeight: FontWeight.w600)),
                ),
              ],
            ),
            const SizedBox(height: 10),
            if (d.status == 'proposee') ...[
              _Level(label: 'Entrée', value: d.entryPrice),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(child: _LevelField(controller: _tp, label: 'Take-profit (€)', invalid: tpValue?.isNaN ?? false)),
                  const SizedBox(width: 8),
                  Expanded(child: _LevelField(controller: _sl, label: 'Stop-loss (€)', invalid: slValue?.isNaN ?? false)),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: FilledButton(
                      onPressed: _busy || invalid ? null : _confirm,
                      child: const Text('Confirmer'),
                    ),
                  ),
                  if (d.patternId != null) ...[
                    const SizedBox(width: 8),
                    Expanded(
                      child: OutlinedButton(onPressed: _busy ? null : _recompute, child: const Text('Recalculer')),
                    ),
                  ],
                ],
              ),
            ] else
              Row(
                children: [
                  Expanded(child: _Level(label: 'Entrée', value: d.entryPrice)),
                  const SizedBox(width: 6),
                  Expanded(child: _Level(label: 'Take-profit', value: d.takeProfit, color: AppColors.positive)),
                  const SizedBox(width: 6),
                  Expanded(child: _Level(label: 'Stop-loss', value: d.stopLoss, color: AppColors.negative)),
                ],
              ),
            if (d.status == 'sortie_proposee') ...[
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: const BoxDecoration(
                  color: AppColors.panelAlt,
                  border: Border(left: BorderSide(color: AppColors.warning, width: 3)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${_exitLabels[d.exitScenario] ?? d.exitScenario ?? 'Sortie'}'
                      '${d.exitVolumeConfirmed == null ? '' : d.exitVolumeConfirmed! ? ' · confirmée par le volume' : ' · volume non confirmé'}',
                      style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 12.5),
                    ),
                    if (d.exitJustification != null) ...[
                      const SizedBox(height: 4),
                      Text(d.exitJustification!, style: TextStyle(fontSize: 12, color: dim)),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: 8),
              FilledButton(
                onPressed: _busy ? null : _confirmExit,
                child: Text(_busy ? 'Clôture…' : 'Confirmer la sortie'),
              ),
            ],
            if (d.status == 'cloturee') ...[
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.all(10),
                color: AppColors.panelAlt,
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        widget.outcome == null
                            ? (_exitLabels[d.exitScenario] ?? 'Clôturée')
                            : '${_resultLabels[widget.outcome!.result] ?? widget.outcome!.result}'
                                ' · le ${DateFormat('dd/MM/yyyy').format(widget.outcome!.closedAt)}',
                        style: TextStyle(fontSize: 12, color: dim),
                      ),
                    ),
                    if (widget.outcome == null)
                      Text('Résultat non disponible', style: TextStyle(fontSize: 11.5, color: dim))
                    else
                      Text(
                        formatPct(widget.outcome!.pnlPct),
                        style: monoTextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                          color: pctColor(widget.outcome!.pnlPct),
                        ),
                      ),
                  ],
                ),
              ),
            ],
            if (_error != null) ...[
              const SizedBox(height: 6),
              Text(_error!, style: const TextStyle(color: AppColors.negative, fontSize: 12)),
            ],
            if (d.rationale != null) ...[
              const SizedBox(height: 8),
              Text(d.rationale!, style: TextStyle(fontSize: 12, color: dim)),
            ],
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton(onPressed: _explain, child: const Text('George explique →')),
            ),
          ],
        ),
      ),
    );
  }
}

class _Level extends StatelessWidget {
  const _Level({required this.label, required this.value, this.color});

  final String label;
  final double? value;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
      decoration: BoxDecoration(color: AppColors.panelAlt, borderRadius: BorderRadius.circular(6)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label.toUpperCase(), style: const TextStyle(fontSize: 9.5, letterSpacing: 0.8, color: AppColors.textDim)),
          Text(_money(value), style: monoTextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: color)),
        ],
      ),
    );
  }
}

class _LevelField extends StatelessWidget {
  const _LevelField({required this.controller, required this.label, required this.invalid});

  final TextEditingController controller;
  final String label;
  final bool invalid;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      keyboardType: const TextInputType.numberWithOptions(decimal: true),
      style: monoTextStyle(fontSize: 13),
      decoration: InputDecoration(
        labelText: label,
        isDense: true,
        errorText: invalid ? 'Nombre > 0' : null,
      ),
    );
  }
}

class _PerformanceView extends ConsumerWidget {
  const _PerformanceView();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final perfAsync = ref.watch(performanceProvider);
    final dim = Theme.of(context).colorScheme.outline;

    return RefreshIndicator(
      onRefresh: () => ref.refresh(performanceProvider.future),
      child: perfAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, st) => ListView(
          children: const [
            EmptyState(
              message: "Performance indisponible — l'API n'expose peut-être pas encore cette route "
                  '(redéploiement Render nécessaire), ou elle est injoignable.',
            ),
          ],
        ),
        data: (perf) {
          final s = perf.summary;
          if (s.count == 0) {
            return ListView(
              children: const [
                EmptyState(
                  message: 'Aucune position clôturée pour l’instant : la performance apparaîtra '
                      'après la première sortie confirmée.',
                ),
              ],
            );
          }
          return ListView(
            padding: const EdgeInsets.all(12),
            children: [
              Text(
                'Positions clôturées uniquement · % bruts, sans frais ni taille de position · total = somme des %',
                style: TextStyle(fontSize: 11.5, color: dim),
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 12,
                runSpacing: 12,
                children: [
                  _Stat(label: 'Positions clôturées', value: '${s.count}'),
                  _Stat(
                    label: 'Taux de réussite',
                    value: s.winRatePct == null ? '—' : '${s.winRatePct!.toStringAsFixed(0)} %',
                    hint: '${s.wins} gagnante(s), ${s.losses} perdante(s)',
                  ),
                  _Stat(label: 'Gain moyen', value: formatPct(s.avgGainPct), color: pctColor(s.avgGainPct)),
                  _Stat(label: 'Perte moyenne', value: formatPct(s.avgLossPct), color: pctColor(s.avgLossPct)),
                  _Stat(label: 'Moyenne par trade', value: formatPct(s.avgPnlPct), color: pctColor(s.avgPnlPct)),
                  _Stat(
                    label: 'Total',
                    value: formatPct(s.totalPnlPct),
                    color: pctColor(s.totalPnlPct),
                    hint: 'somme des %',
                  ),
                ],
              ),
              if (s.count < 10) ...[
                const SizedBox(height: 10),
                Text(
                  'Encore peu de positions clôturées (${s.count}) : ces chiffres ne sont pas significatifs.',
                  style: const TextStyle(fontSize: 12, color: AppColors.warning),
                ),
              ],
              if (perf.byPattern.isNotEmpty) ...[
                const SizedBox(height: 16),
                Text('Par type de figure', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 4),
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: DataTable(
                    columnSpacing: 18,
                    columns: const [
                      DataColumn(label: Text('Figure')),
                      DataColumn(label: Text('Trades'), numeric: true),
                      DataColumn(label: Text('Réussite'), numeric: true),
                      DataColumn(label: Text('Moyenne'), numeric: true),
                      DataColumn(label: Text('Total'), numeric: true),
                    ],
                    rows: [
                      for (final p in perf.byPattern)
                        DataRow(cells: [
                          DataCell(Text(p.patternType)),
                          DataCell(Text('${p.stats.count}', style: monoTextStyle())),
                          DataCell(Text(
                            p.stats.winRatePct == null ? '—' : '${p.stats.winRatePct!.toStringAsFixed(0)} %',
                            style: monoTextStyle(),
                          )),
                          DataCell(Text(
                            formatPct(p.stats.avgPnlPct),
                            style: monoTextStyle(color: pctColor(p.stats.avgPnlPct)),
                          )),
                          DataCell(Text(
                            formatPct(p.stats.totalPnlPct),
                            style: monoTextStyle(color: pctColor(p.stats.totalPnlPct)),
                          )),
                        ]),
                    ],
                  ),
                ),
              ],
            ],
          );
        },
      ),
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat({required this.label, required this.value, this.color, this.hint});

  final String label;
  final String value;
  final Color? color;
  final String? hint;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 150,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label.toUpperCase(), style: const TextStyle(fontSize: 10, letterSpacing: 0.8, color: AppColors.textDim)),
          const SizedBox(height: 2),
          Text(value, style: monoTextStyle(fontSize: 19, fontWeight: FontWeight.w600, color: color)),
          if (hint != null) Text(hint!, style: const TextStyle(fontSize: 11, color: AppColors.textDim)),
        ],
      ),
    );
  }
}
