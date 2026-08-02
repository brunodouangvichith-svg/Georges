import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_theme.dart';
import '../../data/baskets_repository.dart';
import '../../data/decisions_repository.dart';
import '../../data/portfolios_repository.dart';
import '../../data/securities_repository.dart';
import '../../models/decision.dart';
import '../../shared/widgets/response_dialog.dart';
import 'widgets/basket_index_card.dart';
import 'widgets/sector_pie_chart.dart';

const _decisionTypes = ['Achat', 'Renforcer', 'Surveiller', 'Alléger'];
const _confidencePresets = [0, 50, 60, 70, 75];
const _statuses = ['proposee', 'confirmee', 'sortie_proposee', 'cloturee'];
const _statusLabels = {
  'proposee': 'Proposée',
  'confirmee': 'Confirmée',
  'sortie_proposee': 'Sortie proposée',
  'cloturee': 'Clôturée',
};

Color _decisionColor(String type) {
  if (type == 'Achat' || type == 'Renforcer') return AppColors.positive;
  if (type == 'Surveiller') return AppColors.warning;
  return AppColors.negative;
}

Color _scoreColor(double score) {
  if (score >= 75) return AppColors.positive;
  if (score >= 65) return AppColors.warning;
  return AppColors.negative;
}

/// Panier/décisions — miroir simplifié (pour mobile) de
/// web/src/views/Paniers.jsx : KPIs, filtres, table de décisions avec
/// sélection par case à cocher -> création de portefeuille, George Index par
/// panier, répartition sectorielle.
class PaniersScreen extends ConsumerStatefulWidget {
  const PaniersScreen({super.key});

  @override
  ConsumerState<PaniersScreen> createState() => _PaniersScreenState();
}

class _PaniersScreenState extends ConsumerState<PaniersScreen> {
  String _decisionTypeFilter = 'Toutes';
  String _statusFilter = 'Toutes';
  int _minConfidence = 0;
  final Set<int> _checkedIds = {};

  void _openDecisionPrompt(Decision decision) {
    final title = '${decision.symbol} — ${decision.decisionType}';
    final summary = 'Entrée ${decision.entryPrice.toStringAsFixed(2)} €'
        '${decision.takeProfit != null ? ' · Take-profit ${decision.takeProfit!.toStringAsFixed(2)} €' : ''}'
        '${decision.stopLoss != null ? ' · Stop-loss ${decision.stopLoss!.toStringAsFixed(2)} €' : ''}'
        ' · Confiance ${decision.confidence.round()}%';

    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(title),
        content: Text(summary),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(), child: const Text('Fermer')),
          FilledButton(
            onPressed: () {
              Navigator.of(dialogContext).pop();
              showResponseDialog(
                context,
                title: 'George explique — ${decision.symbol}',
                loadingText: 'George réfléchit…',
                action: () async {
                  final result = await ref.read(decisionsRepositoryProvider).explain(decision.id);
                  return result.explanation;
                },
              );
            },
            child: const Text("Demander une analyse à George"),
          ),
        ],
      ),
    );
  }

  void _openCreatePortfolioDialog() {
    final controller = TextEditingController();
    var isSubmitting = false;

    showDialog(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setDialogState) => AlertDialog(
          title: const Text('Créer un portefeuille'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              TextField(
                controller: controller,
                autofocus: true,
                decoration: const InputDecoration(labelText: 'Nom du portefeuille', hintText: 'ex. Portefeuille croissance'),
              ),
              const SizedBox(height: 8),
              Text('${_checkedIds.length} décision${_checkedIds.length > 1 ? 's' : ''} sélectionnée${_checkedIds.length > 1 ? 's' : ''}'),
            ],
          ),
          actions: [
            TextButton(
              onPressed: isSubmitting ? null : () => Navigator.of(dialogContext).pop(),
              child: const Text('❌ Annuler'),
            ),
            FilledButton(
              // `isSubmitting` évite un vrai bug observé en direct : sans ce
              // garde-fou, un double-tap (ou un simple délai réseau) sur
              // "Enregistrer" déclenchait deux appels `create()` avant que le
              // premier n'ait eu le temps de fermer la boîte de dialogue,
              // créant deux portefeuilles identiques (même nom, mêmes
              // décisions) — même précaution déjà en place sur la boîte de
              // dialogue d'inscription (login_screen.dart:_showSignUpDialog).
              onPressed: isSubmitting
                  ? null
                  : () async {
                      final name = controller.text.trim();
                      if (name.isEmpty) return;
                      setDialogState(() => isSubmitting = true);
                      final navigator = Navigator.of(dialogContext);
                      try {
                        await ref.read(portfoliosRepositoryProvider).create(name, _checkedIds.toList());
                        ref.invalidate(portfoliosProvider);
                        if (mounted) setState(() => _checkedIds.clear());
                        navigator.pop();
                        if (mounted) {
                          showDialog<void>(
                            context: context,
                            builder: (confirmContext) => AlertDialog(
                              title: const Text('Portefeuille créé'),
                              content: Text('« $name » a bien été enregistré.'),
                              actions: [
                                TextButton(onPressed: () => Navigator.of(confirmContext).pop(), child: const Text('OK')),
                              ],
                            ),
                          );
                        }
                      } catch (e) {
                        setDialogState(() => isSubmitting = false);
                        if (dialogContext.mounted) {
                          ScaffoldMessenger.of(dialogContext).showSnackBar(SnackBar(content: Text('$e')));
                        }
                      }
                    },
              child: isSubmitting
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('✅ Enregistrer'),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final basketsAsync = ref.watch(basketsProvider);
    final securitiesAsync = ref.watch(securitiesProvider(null));
    final decisionsAsync = ref.watch(decisionsProvider(const DecisionsFilter()));

    final baskets = basketsAsync.value ?? const [];
    final securities = securitiesAsync.value?.items ?? const [];
    final decisions = decisionsAsync.value?.items ?? const [];
    final apiUnreachable = basketsAsync.hasError || securitiesAsync.hasError || decisionsAsync.hasError;

    final decisionCounts = <String, int>{};
    for (final d in decisions) {
      decisionCounts[d.decisionType] = (decisionCounts[d.decisionType] ?? 0) + 1;
    }

    final visibleDecisions = decisions.where((d) {
      return d.confidence >= _minConfidence &&
          (_decisionTypeFilter == 'Toutes' || d.decisionType == _decisionTypeFilter) &&
          (_statusFilter == 'Toutes' || d.status == _statusFilter);
    }).toList();

    return Scaffold(
      appBar: AppBar(title: const Text('Paniers & décisions')),
      floatingActionButton: _checkedIds.isEmpty
          ? null
          : FloatingActionButton.extended(
              onPressed: _openCreatePortfolioDialog,
              icon: const Icon(Icons.add),
              label: Text('Créer un portefeuille (${_checkedIds.length})'),
            ),
      body: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          Row(
            children: [
              Expanded(child: _KpiCard(label: 'Paniers', value: '${baskets.length}', color: Theme.of(context).colorScheme.onSurface)),
              const SizedBox(width: 8),
              Expanded(child: _KpiCard(label: 'Titres suivis', value: '${securities.length}', color: Theme.of(context).colorScheme.onSurface)),
              const SizedBox(width: 8),
              Expanded(child: _KpiCard(label: 'Décisions', value: '${decisions.length}', color: Theme.of(context).colorScheme.onSurface)),
            ],
          ),
          if (apiUnreachable)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Text(
                "Impossible de contacter l'API — si le service vient d'être inactif, le premier appel peut prendre jusqu'à ~50s (réveil du plan gratuit Render), sinon vérifiez la connexion.",
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
          const SizedBox(height: 16),
          Text('Filtres', style: Theme.of(context).textTheme.labelLarge),
          const SizedBox(height: 6),
          _FilterChipsRow(
            label: 'Décision',
            options: const ['Toutes', ..._decisionTypes],
            selected: _decisionTypeFilter,
            onSelected: (v) => setState(() => _decisionTypeFilter = v),
          ),
          _FilterChipsRow(
            label: 'Confiance ≥',
            options: _confidencePresets.map((p) => p == 0 ? 'Toutes' : '$p').toList(),
            selected: _minConfidence == 0 ? 'Toutes' : '$_minConfidence',
            onSelected: (v) => setState(() => _minConfidence = v == 'Toutes' ? 0 : int.parse(v)),
          ),
          _FilterChipsRow(
            label: 'Statut',
            options: const ['Toutes', ..._statuses],
            optionLabels: {for (final s in _statuses) s: _statusLabels[s]!},
            selected: _statusFilter,
            onSelected: (v) => setState(() => _statusFilter = v),
          ),
          const SizedBox(height: 12),
          if (decisions.isEmpty)
            const Text('Aucune décision enregistrée. Lancez python -m engine.propose_decisions ou python -m ingestion.seed_demo.')
          else if (visibleDecisions.isEmpty)
            Text('Aucune décision avec une confiance ≥ $_minConfidence%.')
          else
            ...visibleDecisions.map((d) => _DecisionCard(
                  decision: d,
                  checked: _checkedIds.contains(d.id),
                  onCheckedChanged: (checked) => setState(() {
                    if (checked) {
                      _checkedIds.add(d.id);
                    } else {
                      _checkedIds.remove(d.id);
                    }
                  }),
                  onTap: () => _openDecisionPrompt(d),
                )),
          const SizedBox(height: 16),
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            childAspectRatio: 2.4,
            crossAxisSpacing: 8,
            mainAxisSpacing: 8,
            children: [
              for (final type in _decisionTypes)
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    border: Border.all(color: Theme.of(context).dividerColor),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(type, style: Theme.of(context).textTheme.labelSmall),
                      Text(
                        '${decisionCounts[type] ?? 0}',
                        style: TextStyle(color: _decisionColor(type), fontWeight: FontWeight.bold),
                      ),
                    ],
                  ),
                ),
            ],
          ),
          const SizedBox(height: 20),
          Text('George Index par panier', style: Theme.of(context).textTheme.labelLarge),
          if (baskets.isEmpty)
            const Padding(
              padding: EdgeInsets.only(top: 8),
              child: Text('Aucun panier. Lancez python -m ingestion.seed_demo.'),
            )
          else
            ...baskets.map((b) => BasketIndexCard(basketId: b.id, basketName: b.name)),
          const SizedBox(height: 20),
          Text("Répartition de l'univers par secteur", style: Theme.of(context).textTheme.labelLarge),
          const SizedBox(height: 8),
          SectorPieChart(securities: securities),
          const SizedBox(height: 20),
          Text(
            "Données réelles issues de l'API — la plupart des décisions ci-dessus viennent de figures chartistes "
            'réellement détectées ; quelques-unes plus anciennes restent un jeu de démonstration illustratif.',
            style: Theme.of(context).textTheme.labelSmall,
          ),
        ],
      ),
    );
  }
}

class _KpiCard extends StatelessWidget {
  const _KpiCard({required this.label, required this.value, required this.color});

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(border: Border.all(color: Theme.of(context).dividerColor), borderRadius: BorderRadius.circular(8)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: Theme.of(context).textTheme.labelSmall),
          Text(value, style: monoTextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 16)),
        ],
      ),
    );
  }
}

class _FilterChipsRow extends StatelessWidget {
  const _FilterChipsRow({
    required this.label,
    required this.options,
    required this.selected,
    required this.onSelected,
    this.optionLabels,
  });

  final String label;
  final List<String> options;
  final String selected;
  final ValueChanged<String> onSelected;
  final Map<String, String>? optionLabels;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: Theme.of(context).textTheme.labelSmall),
          const SizedBox(height: 4),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: options
                  .map((o) => Padding(
                        padding: const EdgeInsets.only(right: 6),
                        child: ChoiceChip(
                          label: Text(optionLabels?[o] ?? o),
                          selected: selected == o,
                          onSelected: (_) => onSelected(o),
                        ),
                      ))
                  .toList(),
            ),
          ),
        ],
      ),
    );
  }
}

class _DecisionCard extends StatelessWidget {
  const _DecisionCard({
    required this.decision,
    required this.checked,
    required this.onCheckedChanged,
    required this.onTap,
  });

  final Decision decision;
  final bool checked;
  final ValueChanged<bool> onCheckedChanged;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4),
      child: ListTile(
        onTap: onTap,
        leading: Checkbox(value: checked, onChanged: (v) => onCheckedChanged(v ?? false)),
        title: Row(
          children: [
            Text(decision.symbol, style: const TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(width: 8),
            Text(decision.decisionType, style: TextStyle(color: _decisionColor(decision.decisionType), fontWeight: FontWeight.bold)),
          ],
        ),
        subtitle: Text(
          '${_statusLabels[decision.status] ?? decision.status} · Entrée ${decision.entryPrice.toStringAsFixed(2)} €',
        ),
        trailing: Text(
          '${decision.confidence.round()}%',
          style: TextStyle(color: _scoreColor(decision.confidence), fontWeight: FontWeight.bold),
        ),
      ),
    );
  }
}
