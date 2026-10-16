import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../core/theme/app_theme.dart';
import '../../data/bonds_repository.dart';
import '../../models/bond.dart';
import '../../shared/widgets/empty_state.dart';
import '../../shared/widgets/response_dialog.dart';
import 'bond_history_chart.dart';

/// Onglet « Obligataire » — miroir mobile de web/src/views/Obligataire.jsx
/// (Obligataire Watch, api/routers/bonds.py) : cartes de taux, écart
/// OAT-Bund, pente US, historique, bulletin, alertes actives et seuils
/// modifiables. Convention rappelée à l'écran : une HAUSSE de taux est en
/// rouge, une BAISSE en vert. Aucune valeur fabriquée.
class ObligataireScreen extends ConsumerStatefulWidget {
  const ObligataireScreen({super.key});

  @override
  ConsumerState<ObligataireScreen> createState() => _ObligataireScreenState();
}

class InstrumentMeta {
  const InstrumentMeta(this.label, this.color, {this.width = 1.6, this.dashed = false, this.unit = '%'});

  final String label;
  final Color color;
  final double width;
  final bool dashed;
  final String unit;
}

const instruments = {
  'OAT_FR_10Y': InstrumentMeta('OAT France 10 ans', AppColors.accent, width: 2.4),
  'BUND_DE_10Y': InstrumentMeta('Bund Allemagne 10 ans', AppColors.text),
  'UST_US_10Y': InstrumentMeta('Treasury US 10 ans', AppColors.warning),
  'UST_US_2Y': InstrumentMeta('Treasury US 2 ans', AppColors.textDim, width: 1.4, dashed: true),
  'SPREAD_OAT_BUND_BPS': InstrumentMeta('Spread OAT-Bund', AppColors.textDim, unit: 'pb'),
};

const _historyInstruments = ['OAT_FR_10Y', 'BUND_DE_10Y', 'UST_US_10Y', 'UST_US_2Y'];
const _ranges = [('1 an', 365), ('3 ans', 3 * 365), ('5 ans', 5 * 365)];
const _directionLabel = {'above': 'au-dessus de', 'below': 'en dessous de'};

String labelOf(String code) => instruments[code]?.label ?? code;

class _ObligataireScreenState extends ConsumerState<ObligataireScreen> {
  int _rangeDays = 365;

  void _refresh() {
    showResponseDialog(
      context,
      title: 'Mise à jour des taux',
      loadingText: 'Collecte des taux en cours…',
      shareable: false,
      action: () async {
        final r = await ref.read(bondsRepositoryProvider).refresh();
        invalidateBondData(ref);
        final parts = <String>[
          '${r.instrumentsUpdated.length} instrument(s) mis à jour.',
          if (r.instrumentsFailed.isNotEmpty) 'Échec : ${r.instrumentsFailed.map(labelOf).join(', ')}.',
          '${r.alertsCreated} nouvelle(s) alerte(s).',
        ];
        return parts.join('\n');
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final dashboardAsync = ref.watch(bondDashboardProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Obligataire'),
        actions: [
          IconButton(tooltip: 'Mettre à jour les taux', icon: const Icon(Icons.refresh), onPressed: _refresh),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          invalidateBondData(ref);
          await ref.read(bondDashboardProvider.future);
        },
        child: ListView(
          padding: const EdgeInsets.all(12),
          children: [
            const Text(
              'Hausse de taux en rouge (financement plus cher), baisse en vert.',
              style: TextStyle(fontSize: 11.5, color: AppColors.textDim),
            ),
            const SizedBox(height: 10),
            dashboardAsync.when(
              loading: () => const Padding(
                padding: EdgeInsets.all(24),
                child: Center(child: CircularProgressIndicator()),
              ),
              error: (e, st) => const EmptyState(
                message: "Impossible de contacter l'API — le serveur met parfois 1 à 2 minutes à se "
                    'réveiller, réessaie dans un instant.',
              ),
              data: (dashboard) => _Dashboard(dashboard: dashboard),
            ),
            const SizedBox(height: 12),
            _Section(
              title: 'Historique',
              trailing: Wrap(
                spacing: 6,
                children: [
                  for (final r in _ranges)
                    ChoiceChip(
                      label: Text(r.$1),
                      selected: _rangeDays == r.$2,
                      onSelected: (_) => setState(() => _rangeDays = r.$2),
                    ),
                ],
              ),
              child: _History(rangeDays: _rangeDays),
            ),
            const _BulletinSection(),
            const _ActiveAlertsSection(),
            const _ThresholdsSection(),
          ],
        ),
      ),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({required this.title, required this.child, this.trailing});

  final String title;
  final Widget child;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title.toUpperCase(), style: const TextStyle(fontSize: 10.5, letterSpacing: 0.8, color: AppColors.textDim)),
            if (trailing != null) ...[const SizedBox(height: 6), trailing!],
            const SizedBox(height: 8),
            child,
          ],
        ),
      ),
    );
  }
}

class _Dashboard extends StatelessWidget {
  const _Dashboard({required this.dashboard});

  final BondDashboard dashboard;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final card in dashboard.cards) YieldCard(card: card),
        Row(
          children: [
            Expanded(
              child: _SpreadCard(
                title: 'Écart OAT-Bund',
                value: dashboard.spreadOatBundBps,
                hint: 'prime de risque France',
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: _SpreadCard(
                title: 'Pente US 10a-2a',
                value: dashboard.usCurveSlopeBps,
                hint: 'négative = courbe inversée',
              ),
            ),
          ],
        ),
      ],
    );
  }
}

/// Carte d'un taux avec ses variations 24h/7j/30j.
class YieldCard extends StatelessWidget {
  const YieldCard({super.key, required this.card});

  final BondYieldCard card;

  @override
  Widget build(BuildContext context) {
    final meta = instruments[card.instrument];
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 9,
                  height: 9,
                  decoration: BoxDecoration(color: meta?.color ?? AppColors.textDim, shape: BoxShape.circle),
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    (meta?.label ?? card.instrument).toUpperCase(),
                    style: const TextStyle(fontSize: 10.5, letterSpacing: 0.8, color: AppColors.textDim),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            if (card.valuePct == null)
              const Text(
                'Donnée indisponible (aucune collecte réussie)',
                style: TextStyle(fontSize: 13, color: AppColors.textDim),
              )
            else ...[
              Text('${card.valuePct!.toStringAsFixed(2)} %', style: monoTextStyle(fontSize: 22, fontWeight: FontWeight.w600)),
              const SizedBox(height: 4),
              Wrap(
                spacing: 12,
                children: [
                  Variation(label: '24h', bps: card.variationsBps['24h']),
                  Variation(label: '7j', bps: card.variationsBps['7j']),
                  Variation(label: '30j', bps: card.variationsBps['30j']),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                'Observé le ${card.observedAt ?? '—'} · ${card.sourceName ?? '—'}',
                style: const TextStyle(fontSize: 11, color: AppColors.textDim),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Variation en points de base : ▲ rouge = hausse de taux, ▼ vert = baisse.
class Variation extends StatelessWidget {
  const Variation({super.key, required this.label, required this.bps});

  final String label;
  final double? bps;

  @override
  Widget build(BuildContext context) {
    final value = bps;
    if (value == null) {
      return Text('$label n/d', style: monoTextStyle(fontSize: 11.5, color: AppColors.textDim));
    }
    final flat = value == 0;
    final up = value > 0;
    final color = flat ? AppColors.textDim : (up ? AppColors.negative : AppColors.positive);
    final arrow = flat ? '=' : (up ? '▲' : '▼');
    return Semantics(
      label: '$label ${flat ? 'stable' : up ? 'hausse' : 'baisse'} de ${value.abs().toStringAsFixed(0)} points de base',
      child: ExcludeSemantics(
        child: Text('$label $arrow ${value.abs().toStringAsFixed(0)} pb', style: monoTextStyle(fontSize: 11.5, color: color)),
      ),
    );
  }
}

class _SpreadCard extends StatelessWidget {
  const _SpreadCard({required this.title, required this.value, required this.hint});

  final String title;
  final double? value;
  final String hint;

  @override
  Widget build(BuildContext context) {
    final v = value;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.panelAlt,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.hairline),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title.toUpperCase(), style: const TextStyle(fontSize: 10, letterSpacing: 0.8, color: AppColors.textDim)),
          const SizedBox(height: 4),
          Text(
            v == null ? '—' : '${v >= 0 ? '+' : ''}${v.toStringAsFixed(0)} pb',
            style: monoTextStyle(fontSize: 20, fontWeight: FontWeight.w600),
          ),
          Text(
            v == null ? 'Données non contemporaines ou indisponibles' : hint,
            style: const TextStyle(fontSize: 11, color: AppColors.textDim),
          ),
        ],
      ),
    );
  }
}

class _History extends ConsumerWidget {
  const _History({required this.rangeDays});

  final int rangeDays;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncs = {for (final code in _historyInstruments) code: ref.watch(bondHistoryProvider(code))};
    // Spinner seulement tant qu'une série n'a encore ni valeur ni erreur :
    // `isLoading` reste vrai pendant un rafraîchissement (valeur précédente
    // conservée) et pendant les nouvelles tentatives automatiques de
    // Riverpod 3 après une erreur — une seule série en échec bloquerait
    // sinon le graphique des trois autres.
    if (asyncs.values.any((a) => !a.hasValue && !a.hasError)) {
      return const SizedBox(height: 120, child: Center(child: CircularProgressIndicator()));
    }
    if (asyncs.values.every((a) => a.hasError)) {
      return const Text('Historique indisponible.', style: TextStyle(color: AppColors.textDim));
    }
    final cutoff = DateTime.now().subtract(Duration(days: rangeDays));
    final series = [
      for (final code in _historyInstruments)
        BondSeries(
          label: instruments[code]!.label,
          color: instruments[code]!.color,
          width: instruments[code]!.width,
          dashed: instruments[code]!.dashed,
          points: (asyncs[code]!.value ?? const <BondHistoryPoint>[])
              .where((p) => p.observedAt.isAfter(cutoff))
              .toList()
            ..sort((a, b) => a.observedAt.compareTo(b.observedAt)),
        ),
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        BondHistoryChart(series: series),
        const SizedBox(height: 6),
        const Text(
          'OAT et Bund sont des séries mensuelles (OCDE), les Treasuries quotidiennes.',
          style: TextStyle(fontSize: 11, color: AppColors.textDim),
        ),
      ],
    );
  }
}

class _BulletinSection extends ConsumerWidget {
  const _BulletinSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final bulletinAsync = ref.watch(bondBulletinProvider);
    return _Section(
      title: 'Bulletin du jour',
      child: bulletinAsync.when(
        loading: () => const Text('Chargement…', style: TextStyle(color: AppColors.textDim)),
        error: (e, st) => const Text('Bulletin indisponible.', style: TextStyle(color: AppColors.textDim)),
        data: (b) => Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SelectableText(b.bulletin, style: const TextStyle(fontSize: 13, height: 1.45)),
            const SizedBox(height: 6),
            Text(
              'Généré le ${DateFormat('dd/MM/yyyy HH:mm').format(b.generatedAt.toLocal())}',
              style: const TextStyle(fontSize: 11, color: AppColors.textDim),
            ),
          ],
        ),
      ),
    );
  }
}

class _ActiveAlertsSection extends ConsumerWidget {
  const _ActiveAlertsSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final alertsAsync = ref.watch(bondActiveAlertsProvider);
    return _Section(
      title: 'Alertes actives',
      child: alertsAsync.when(
        loading: () => const Text('Chargement…', style: TextStyle(color: AppColors.textDim)),
        error: (e, st) => const Text('Alertes indisponibles.', style: TextStyle(color: AppColors.textDim)),
        data: (alerts) => alerts.isEmpty
            ? const Text('Aucune alerte active.', style: TextStyle(color: AppColors.textDim))
            : Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  for (final a in alerts)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Container(
                        padding: const EdgeInsets.all(10),
                        decoration: const BoxDecoration(
                          color: AppColors.panelAlt,
                          border: Border(left: BorderSide(color: AppColors.warning, width: 3)),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(a.message, style: const TextStyle(fontSize: 12.5)),
                            const SizedBox(height: 2),
                            Text(
                              DateFormat('dd/MM/yyyy HH:mm').format(a.triggeredAt.toLocal()),
                              style: const TextStyle(fontSize: 11, color: AppColors.textDim),
                            ),
                          ],
                        ),
                      ),
                    ),
                ],
              ),
      ),
    );
  }
}

class _ThresholdsSection extends ConsumerWidget {
  const _ThresholdsSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final thresholdsAsync = ref.watch(bondThresholdsProvider);
    return _Section(
      title: 'Seuils d’alerte',
      child: thresholdsAsync.when(
        loading: () => const Text('Chargement…', style: TextStyle(color: AppColors.textDim)),
        error: (e, st) => const Text('Seuils indisponibles.', style: TextStyle(color: AppColors.textDim)),
        data: (thresholds) => thresholds.isEmpty
            ? const Text('Aucun seuil configuré.', style: TextStyle(color: AppColors.textDim))
            : Column(
                children: [
                  for (final t in thresholds)
                    ThresholdRow(key: ValueKey('${t.id}-${t.updatedAt.toIso8601String()}'), threshold: t),
                ],
              ),
      ),
    );
  }
}

/// Un seuil modifiable en place. La clé inclut `updatedAt`, donc l'état local
/// repart de la valeur serveur après chaque enregistrement réussi.
class ThresholdRow extends ConsumerStatefulWidget {
  const ThresholdRow({super.key, required this.threshold});

  final BondAlertThreshold threshold;

  @override
  ConsumerState<ThresholdRow> createState() => _ThresholdRowState();
}

class _ThresholdRowState extends ConsumerState<ThresholdRow> {
  late final TextEditingController _value;
  late bool _enabled;
  bool _saving = false;
  String? _error;

  BondAlertThreshold get t => widget.threshold;

  @override
  void initState() {
    super.initState();
    _value = TextEditingController(text: t.thresholdPct.toString());
    _value.addListener(() => setState(() {}));
    _enabled = t.enabled;
  }

  @override
  void dispose() {
    _value.dispose();
    super.dispose();
  }

  double? get _parsed => double.tryParse(_value.text.trim().replaceAll(',', '.'));

  Future<void> _save() async {
    final parsed = _parsed;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await ref.read(bondsRepositoryProvider).updateThreshold(
            t.id,
            thresholdPct: parsed != null && parsed != t.thresholdPct ? parsed : null,
            enabled: _enabled != t.enabled ? _enabled : null,
          );
      ref.invalidate(bondThresholdsProvider);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final parsed = _parsed;
    final valid = parsed != null;
    final dirty = (valid && parsed != t.thresholdPct) || _enabled != t.enabled;
    final unit = instruments[t.instrument]?.unit ?? '%';

    return Container(
      padding: const EdgeInsets.symmetric(vertical: 8),
      decoration: const BoxDecoration(border: Border(bottom: BorderSide(color: AppColors.hairline))),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text.rich(
            TextSpan(
              children: [
                TextSpan(text: labelOf(t.instrument), style: const TextStyle(fontWeight: FontWeight.w600)),
                TextSpan(
                  text: '  alerte ${_directionLabel[t.direction] ?? t.direction}',
                  style: const TextStyle(color: AppColors.textDim),
                ),
              ],
            ),
            style: const TextStyle(fontSize: 12.5),
          ),
          const SizedBox(height: 6),
          Row(
            children: [
              SizedBox(
                width: 96,
                child: TextField(
                  controller: _value,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: true),
                  textAlign: TextAlign.right,
                  style: monoTextStyle(fontSize: 13),
                  decoration: InputDecoration(
                    isDense: true,
                    suffixText: unit,
                    errorText: valid ? null : 'Invalide',
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Switch(value: _enabled, onChanged: (v) => setState(() => _enabled = v)),
              const Text('Active', style: TextStyle(fontSize: 12)),
              const Spacer(),
              // Bouton icône (et non texte) : la ligne doit tenir sur ~310 px
              // de large une fois le champ et l'interrupteur placés.
              IconButton.filled(
                tooltip: 'Enregistrer',
                onPressed: dirty && valid && !_saving ? _save : null,
                icon: _saving
                    ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.check),
              ),
            ],
          ),
          if (_error != null) Text(_error!, style: const TextStyle(color: AppColors.negative, fontSize: 11.5)),
        ],
      ),
    );
  }
}
