"""Internationalization strings for SynthEd reports."""

from __future__ import annotations

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        # Section headings
        "title": "SynthEd Report",
        "executive_summary": "Executive Summary",
        "population_demographics": "Population Demographics",
        "simulation_results": "Simulation Results",
        "validation_report": "Validation Report",
        "configuration": "Configuration",
        # Metadata
        "generated_on": "Generated on",
        "version": "Version",
        "students": "Students",
        "seed": "Seed",
        "semesters": "Semesters",
        "duration": "Duration",
        "seconds": "seconds",
        # KPI labels
        "dropout_rate": "Dropout Rate",
        "mean_engagement": "Mean Engagement",
        "mean_gpa": "Mean GPA",
        "validation_grade": "Validation Grade",
        # Demographics
        "age_distribution": "Age Distribution",
        "gender_distribution": "Gender Distribution",
        "employment_rate": "Employment Rate",
        "male": "Male",
        "female": "Female",
        "employed": "Employed",
        "not_employed": "Not Employed",
        # Simulation chart titles
        "dropout_timeline": "Dropout Timeline",
        "engagement_distribution": "Engagement Distribution",
        "gpa_distribution": "GPA Distribution",
        "validation_radar": "Validation Radar",
        # Validation table headers
        "test_name": "Test Name",
        "metric": "Metric",
        "synthetic_value": "Synthetic Value",
        "reference_value": "Reference Value",
        "p_value": "p-value",
        "result": "Result",
        "pass": "Pass",
        "fail": "Fail",
        "passed_of_total": "{passed} / {total} passed",
        # Config group labels
        "demographics": "Demographics",
        "academic": "Academic",
        "risk_factors": "Risk Factors",
        "grading": "Grading",
        "institutional": "Institutional",
        # Table column headers
        "parameter": "Parameter",
        "value": "Value",
        "count": "Count",
        "week": "Week",
        "final_engagement": "Final Engagement",
        "cumulative_gpa": "Cumulative GPA",
        "cumulative_dropout": "Cumulative Dropout",
    },
    "tr": {
        # Section headings
        "title": "SynthEd Raporu",
        "executive_summary": "Yonetici Ozeti",
        "population_demographics": "Populasyon Demografisi",
        "simulation_results": "Simulasyon Sonuclari",
        "validation_report": "Dogrulama Raporu",
        "configuration": "Yapilandirma",
        # Metadata
        "generated_on": "Olusturulma tarihi",
        "version": "Surum",
        "students": "Ogrenci",
        "seed": "Tohum",
        "semesters": "Donem",
        "duration": "Sure",
        "seconds": "saniye",
        # KPI labels
        "dropout_rate": "Birakma Orani",
        "mean_engagement": "Ortalama Katilim",
        "mean_gpa": "Ortalama GPA",
        "validation_grade": "Dogrulama Notu",
        # Demographics
        "age_distribution": "Yas Dagilimi",
        "gender_distribution": "Cinsiyet Dagilimi",
        "employment_rate": "Istihdam Orani",
        "male": "Erkek",
        "female": "Kadin",
        "employed": "Calisan",
        "not_employed": "Calismayan",
        # Simulation chart titles
        "dropout_timeline": "Birakma Zaman Cizelgesi",
        "engagement_distribution": "Katilim Dagilimi",
        "gpa_distribution": "GPA Dagilimi",
        "validation_radar": "Dogrulama Radari",
        # Validation table headers
        "test_name": "Test Adi",
        "metric": "Metrik",
        "synthetic_value": "Sentetik Deger",
        "reference_value": "Referans Deger",
        "p_value": "p-degeri",
        "result": "Sonuc",
        "pass": "Gecti",
        "fail": "Kaldi",
        "passed_of_total": "{passed} / {total} gecti",
        # Config group labels
        "demographics": "Demografik",
        "academic": "Akademik",
        "risk_factors": "Risk Faktorleri",
        "grading": "Notlandirma",
        "institutional": "Kurumsal",
        # Table column headers
        "parameter": "Parametre",
        "value": "Deger",
        "count": "Sayi",
        "week": "Hafta",
        "final_engagement": "Son Katilim",
        "cumulative_gpa": "Kumulatif GPA",
        "cumulative_dropout": "Kumulatif Birakma",
    },
}
