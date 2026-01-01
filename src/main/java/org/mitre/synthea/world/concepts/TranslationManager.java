package org.mitre.synthea.world.concepts;

import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;

import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.lang.reflect.Type;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

import org.mitre.synthea.helpers.Config;

/**
 * TranslationManager handles loading and retrieving translations for medical codes.
 * It supports translating SNOMED-CT, RxNorm, LOINC, and other code systems
 * to French when the country code is set to FR.
 */
public class TranslationManager {

  private static TranslationManager instance;
  private static boolean initialized = false;

  /** Map of code system to (code -> translated display) mappings. */
  private Map<String, Map<String, String>> translations;

  /** Whether French translation is enabled. */
  private boolean frenchEnabled;

  /**
   * Private constructor for singleton pattern.
   */
  private TranslationManager() {
    translations = new HashMap<>();
    String countryCode = Config.get("generate.geography.country_code", "US");
    frenchEnabled = "FR".equals(countryCode);

    if (frenchEnabled) {
      loadTranslations();
    }
  }

  /**
   * Get the singleton instance of TranslationManager.
   * @return the TranslationManager instance
   */
  public static synchronized TranslationManager getInstance() {
    if (instance == null) {
      instance = new TranslationManager();
      initialized = true;
    }
    return instance;
  }

  /**
   * Check if the TranslationManager has been initialized.
   * @return true if initialized
   */
  public static boolean isInitialized() {
    return initialized;
  }

  /**
   * Load all translation files.
   */
  private void loadTranslations() {
    // Load SNOMED-CT translations (conditions/diagnoses)
    loadTranslationFile("SNOMED-CT", "translations/snomed_ct_fr.json");
    loadTranslationFile("http://snomed.info/sct", "translations/snomed_ct_fr.json");

    // Load RxNorm translations (medications)
    loadTranslationFile("RxNorm", "translations/rxnorm_fr.json");
    loadTranslationFile("http://www.nlm.nih.gov/research/umls/rxnorm", "translations/rxnorm_fr.json");

    // Load LOINC translations (observations/lab results)
    loadTranslationFile("LOINC", "translations/loinc_fr.json");
    loadTranslationFile("http://loinc.org", "translations/loinc_fr.json");

    // Load CVX translations (vaccines)
    loadTranslationFile("CVX", "translations/cvx_fr.json");
    loadTranslationFile("http://hl7.org/fhir/sid/cvx", "translations/cvx_fr.json");

    // Load CPT translations (procedures)
    loadTranslationFile("CPT", "translations/cpt_fr.json");
    loadTranslationFile("http://www.ama-assn.org/go/cpt", "translations/cpt_fr.json");
  }

  /**
   * Load a single translation file.
   * @param system the code system identifier
   * @param filename the resource path to the translation file
   */
  private void loadTranslationFile(String system, String filename) {
    try (InputStream is = getClass().getClassLoader().getResourceAsStream(filename)) {
      if (is != null) {
        InputStreamReader reader = new InputStreamReader(is, StandardCharsets.UTF_8);
        Type type = new TypeToken<Map<String, String>>() {}.getType();
        Map<String, String> codeMap = new Gson().fromJson(reader, type);
        if (codeMap != null) {
          translations.put(system, codeMap);
        }
      }
    } catch (IOException e) {
      // Silently ignore missing translation files - will fall back to English
    }
  }

  /**
   * Get the translated display text for a code.
   * @param system the code system (e.g., "SNOMED-CT", "RxNorm")
   * @param code the code value
   * @return the translated display text, or null if no translation found
   */
  public String getTranslation(String system, String code) {
    if (!frenchEnabled || system == null || code == null) {
      return null;
    }

    Map<String, String> systemTranslations = translations.get(system);
    if (systemTranslations != null) {
      return systemTranslations.get(code);
    }
    return null;
  }

  /**
   * Static convenience method to get a translation.
   * @param system the code system
   * @param code the code value
   * @param defaultDisplay the default display if no translation found
   * @return the translated display or the default
   */
  public static String translate(String system, String code, String defaultDisplay) {
    TranslationManager manager = getInstance();
    String translation = manager.getTranslation(system, code);
    return translation != null ? translation : defaultDisplay;
  }

  /**
   * Check if French translations are enabled.
   * @return true if French translations are enabled
   */
  public boolean isFrenchEnabled() {
    return frenchEnabled;
  }

  /**
   * Get the number of translations loaded for a given system.
   * @param system the code system
   * @return the number of translations
   */
  public int getTranslationCount(String system) {
    Map<String, String> systemTranslations = translations.get(system);
    return systemTranslations != null ? systemTranslations.size() : 0;
  }

  /**
   * Reset the singleton instance (useful for testing).
   */
  public static synchronized void reset() {
    instance = null;
    initialized = false;
  }
}
