import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api_client.dart';

/// Instance unique du client HTTP, partagée par tous les repositories.
final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());
