import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Identité visuelle portée depuis `web/src/index.css` — les mêmes valeurs
/// exactes (hex, polices), pas une réinterprétation. George a déjà une
/// vraie identité "terminal de trading" côté web (fond bleu marine très
/// sombre, chiffres en tabulaire, code couleur positif/négatif) ; la
/// reprendre fidèlement ici est un choix plus fort et plus cohérent que
/// d'en inventer une nouvelle pour le mobile.
class AppColors {
  AppColors._();

  static const bg = Color(0xFF0F1626);
  static const panel = Color(0xFF17203A);
  static const panelAlt = Color(0xFF1C2748);
  static const hairline = Color(0xFF2B3660);
  static const text = Color(0xFFEEF1F8);
  static const textDim = Color(0xFF8B96B8);
  static const accent = Color(0xFF4D7FE0);
  static const accentDim = Color(0xFF2C3F6E);
  static const positive = Color(0xFF2FBF82);
  static const warning = Color(0xFFE3A344);
  static const negative = Color(0xFFE2555F);
}

/// Style à utiliser pour tout chiffre financier (prix, %, score, PnL) — la
/// signature visuelle du terminal : toujours en `IBM Plex Mono`, chiffres
/// tabulaires pour un alignement propre en colonne, exactement comme
/// `.mono { font-variant-numeric: tabular-nums }` sur le web.
TextStyle monoTextStyle({double? fontSize, FontWeight? fontWeight, Color? color}) {
  return GoogleFonts.ibmPlexMono(
    fontSize: fontSize,
    fontWeight: fontWeight,
    color: color,
    fontFeatures: const [FontFeature.tabularFigures()],
  );
}

ThemeData buildAppTheme() {
  final base = ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    scaffoldBackgroundColor: AppColors.bg,
    colorScheme: const ColorScheme.dark(
      surface: AppColors.bg,
      onSurface: AppColors.text,
      primary: AppColors.accent,
      onPrimary: AppColors.text,
      primaryContainer: AppColors.accentDim,
      onPrimaryContainer: AppColors.text,
      secondary: AppColors.accent,
      error: AppColors.negative,
      onError: AppColors.text,
      // `outline` sert de couleur "texte atténué" dans tout le reste de
      // l'app (existant avant cette passe : basket_index_card.dart,
      // candlestick_chart.dart, empty_state.dart) — pas une bordure.
      // `outlineVariant` porte le vrai hairline pour les bordures.
      outline: AppColors.textDim,
      outlineVariant: AppColors.hairline,
      surfaceContainerHighest: AppColors.panelAlt,
      onSurfaceVariant: AppColors.textDim,
    ),
  );

  // Space Grotesk pour les titres/l'identité ("George", titres d'écran),
  // Inter pour le corps — même répartition des rôles que web/index.css
  // (`.display` vs police par défaut du body).
  final textTheme = GoogleFonts.interTextTheme(base.textTheme).copyWith(
    displaySmall: GoogleFonts.spaceGrotesk(fontWeight: FontWeight.bold, color: AppColors.text),
    headlineSmall: GoogleFonts.spaceGrotesk(fontWeight: FontWeight.bold, color: AppColors.text),
    titleLarge: GoogleFonts.spaceGrotesk(fontWeight: FontWeight.w600, color: AppColors.text),
    titleMedium: GoogleFonts.spaceGrotesk(fontWeight: FontWeight.w600, color: AppColors.text),
  );

  return base.copyWith(
    textTheme: textTheme,
    appBarTheme: AppBarTheme(
      backgroundColor: AppColors.panel,
      foregroundColor: AppColors.text,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      shape: const Border(bottom: BorderSide(color: AppColors.hairline)),
      titleTextStyle: GoogleFonts.spaceGrotesk(fontWeight: FontWeight.bold, color: AppColors.text, fontSize: 20),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: AppColors.panel,
      surfaceTintColor: Colors.transparent,
      indicatorColor: AppColors.accentDim,
      labelTextStyle: WidgetStateProperty.resolveWith(
        // 11 * 1.20 : taille demandée pour les libellés "Univers"/"Paniers"/"Portefeuille".
        (states) => GoogleFonts.inter(
          fontSize: 13.2,
          fontWeight: FontWeight.w600,
          color: states.contains(WidgetState.selected) ? AppColors.text : AppColors.textDim,
        ),
      ),
      iconTheme: WidgetStateProperty.resolveWith(
        (states) => IconThemeData(color: states.contains(WidgetState.selected) ? AppColors.accent : AppColors.textDim),
      ),
    ),
    cardTheme: CardThemeData(
      color: AppColors.panel,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: AppColors.hairline),
      ),
    ),
    dividerTheme: const DividerThemeData(color: AppColors.hairline, thickness: 1, space: 1),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: AppColors.panelAlt,
      labelStyle: GoogleFonts.inter(color: AppColors.textDim),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: AppColors.hairline)),
      enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: AppColors.hairline)),
      focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: AppColors.accent, width: 1.5)),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: AppColors.accent,
        foregroundColor: Colors.white,
        textStyle: GoogleFonts.inter(fontWeight: FontWeight.w600),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: AppColors.text,
        side: const BorderSide(color: AppColors.hairline),
        textStyle: GoogleFonts.inter(fontWeight: FontWeight.w600),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(foregroundColor: AppColors.accent, textStyle: GoogleFonts.inter(fontWeight: FontWeight.w600)),
    ),
    listTileTheme: const ListTileThemeData(iconColor: AppColors.textDim, textColor: AppColors.text),
    dialogTheme: DialogThemeData(
      backgroundColor: AppColors.panel,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14), side: const BorderSide(color: AppColors.hairline)),
    ),
    snackBarTheme: SnackBarThemeData(
      backgroundColor: AppColors.panelAlt,
      contentTextStyle: GoogleFonts.inter(color: AppColors.text),
    ),
  );
}
