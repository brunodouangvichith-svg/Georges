import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/providers.dart';
import '../models/energy_price.dart';

/// Miroir de web/src/api/queries.js:useEnergyPrices — liste brute (pas de
/// `Page[T]`), 6 lignes au maximum (une par matière première suivie).
class EnergyPricesRepository {
  EnergyPricesRepository(this._ref);

  final Ref _ref;

  Future<List<EnergyPrice>> fetch() async {
    final client = _ref.read(apiClientProvider);
    final json = await client.get('/energy-prices');
    return (json as List).map((e) => EnergyPrice.fromJson(e as Map<String, dynamic>)).toList();
  }
}

final energyPricesRepositoryProvider = Provider<EnergyPricesRepository>((ref) => EnergyPricesRepository(ref));

final energyPricesProvider = FutureProvider.autoDispose<List<EnergyPrice>>((ref) {
  return ref.read(energyPricesRepositoryProvider).fetch();
});
