/* ==========================================================================
   ELYON · BUSINESS-TYPE DESIGN TEMPLATES
   --------------------------------------------------------------------------
   Each template skins the demo page for one type of business: palette,
   Google Fonts pairing, background motif and industry-tailored suggested
   test questions (Mexican Spanish). Applied by demo-page.js via CSS custom
   properties, so adding a template here instantly works for any demo entry
   in demo-config.js that references it (template: '<key>').

   PALETTE CONTRACT (all 6-digit hex, WCAG-validated):
     bg / surface     page background + raised surfaces
     ink / inkSoft    primary + secondary text on bg           (>= 4.5:1)
     accent           buttons, badges, highlights              (>= 3:1 on bg)
     accentDark       hover state of accent
     onAccent         text on accent                           (>= 4.5:1)
     cardBg / cardInk the widget card + conversion band        (>= 4.5:1)
     rule             hairline borders on bg

   To add a business type: copy a block, adjust, and reference its key from
   demo-config.js. Keep the palette contract or buttons/text lose contrast.
   ========================================================================== */

var ELYON_TEMPLATES = {
  automotive: {
    label: "Taller automotriz",
    vibe: "Workshop-grade steel and asphalt neutrals cut with a true safety-orange signal accent — technical and calibrated, like a torque-spec sheet pinned above a clean service bay.",
    palette: {
      bg: "#F2F3F4",
      surface: "#E7EAEC",
      ink: "#14181B",
      inkSoft: "#444C52",
      accent: "#C94F0A",
      accentDark: "#B84806",
      onAccent: "#FFFFFF",
      cardBg: "#22282D",
      cardInk: "#F5F7F8",
      rule: "#C7CDD2"
    },
    fontCss: "https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700;800&family=Barlow:wght@400;500;600&display=swap",
    displayFamily: "'Barlow Condensed', 'Arial Narrow', Arial, sans-serif",
    bodyFamily: "'Barlow', 'Helvetica Neue', Arial, sans-serif",
    motif: "lines",
    questions_es: [
      "Quiero agendar una cita para el servicio de mi carro, ¿tienen lugar esta semana?",
      "¿Cuánto me sale la revisión de frenos y en cuánto tiempo me entregan el coche?",
      "¿Me pueden mandar la cotización por WhatsApp cuando esté lista?"
    ]
  },
  dental: {
    label: "Clínica / consultorio",
    vibe: "Airy clinical calm — porcelain-white page with soft aqua accents and a deep pine-teal widget card, like a modern consultorio dental: hygienic, warm, and quietly premium rather than tech-blue SaaS.",
    palette: {
      bg: "#F5FAF9",
      surface: "#E7F3F0",
      ink: "#0C2B2B",
      inkSoft: "#3F6360",
      accent: "#0E7C72",
      accentDark: "#0A5F58",
      onAccent: "#FFFFFF",
      cardBg: "#0E3230",
      cardInk: "#EAF7F4",
      rule: "#C9DEDA"
    },
    fontCss: "https://fonts.googleapis.com/css2?family=Fraunces:wght@600;700&family=Manrope:wght@400;500;700&display=swap",
    displayFamily: "'Fraunces', Georgia, 'Times New Roman', serif",
    bodyFamily: "'Manrope', 'Segoe UI', Helvetica, Arial, sans-serif",
    motif: "dots",
    questions_es: [
      "¿Me puede agendar una cita para una limpieza dental esta semana?",
      "¿Cuánto cuesta más o menos una resina o un blanqueamiento?",
      "¿Me pueden mandar la confirmación de la cita y la ubicación por WhatsApp?"
    ]
  },
  restaurant: {
    label: "Restaurante",
    vibe: "Warm trattoria hospitality: cream linen page, deep bottle-green menu-board card, brick-terracotta accent, and an editorial serif that feels like a hand-set dinner menu.",
    palette: {
      bg: "#FBF4E8",
      surface: "#F4E8D3",
      ink: "#2E1F14",
      inkSoft: "#6E5847",
      accent: "#A63A20",
      accentDark: "#8F3416",
      onAccent: "#FFF6EB",
      cardBg: "#1F3527",
      cardInk: "#F3EAD8",
      rule: "#E2D2B8"
    },
    fontCss: "https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600;700&family=Karla:wght@400;500;700&display=swap",
    displayFamily: "'Playfair Display', Georgia, 'Times New Roman', serif",
    bodyFamily: "'Karla', 'Helvetica Neue', Arial, sans-serif",
    motif: "lines",
    questions_es: [
      "Quiero reservar una mesa para cuatro este sábado en la noche, ¿tienen lugar?",
      "¿Tienen opciones vegetarianas en el menú?",
      "¿Me pueden mandar el menú por WhatsApp?"
    ]
  },
  beauty: {
    label: "Salón de belleza / spa",
    vibe: "Editorial spa elegance: blush-paper page with deep plum ink, a dusty-rose accent, and a dark plum widget card that feels like a velvet vanity tray.",
    palette: {
      bg: "#FBF5F3",
      surface: "#F5EAE6",
      ink: "#43242F",
      inkSoft: "#705462",
      accent: "#9C4A63",
      accentDark: "#7E3950",
      onAccent: "#FFFFFF",
      cardBg: "#3B2230",
      cardInk: "#F7ECEF",
      rule: "#E6D3D3"
    },
    fontCss: "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700&family=Mulish:wght@400;600;700&display=swap",
    displayFamily: "'Cormorant Garamond', 'Times New Roman', Georgia, serif",
    bodyFamily: "'Mulish', 'Segoe UI', Helvetica, Arial, sans-serif",
    motif: "dots",
    questions_es: [
      "Hola, ¿me pueden agendar una cita para corte y peinado este sábado?",
      "¿Qué precio tiene el balayage y más o menos cuánto tiempo tarda?",
      "¿Me pueden mandar la confirmación y la lista de servicios por WhatsApp?"
    ]
  },
  fitness: {
    label: "Gimnasio / estudio fitness",
    vibe: "Night-gym energy: near-black charcoal with a green undertone, one electric volt accent, condensed poster headlines and diagonal speed lines — bold, sweaty, premium athletic, zero SaaS-blue.",
    palette: {
      bg: "#0C0D0B",
      surface: "#15170E",
      ink: "#F4F6EF",
      inkSoft: "#A9AF9C",
      accent: "#CCFF00",
      accentDark: "#A8D400",
      onAccent: "#0C0D0B",
      cardBg: "#F6F8EE",
      cardInk: "#161807",
      rule: "#3A3F28"
    },
    fontCss: "https://fonts.googleapis.com/css2?family=Anton&family=Barlow:wght@400;500;700&display=swap",
    displayFamily: "'Anton', 'Arial Narrow', Impact, sans-serif",
    bodyFamily: "'Barlow', 'Helvetica Neue', Arial, sans-serif",
    motif: "lines",
    questions_es: [
      "Quiero apartar un lugar en la clase de mañana, ¿todavía hay cupo?",
      "¿Cuánto cuesta la membresía mensual y qué incluye?",
      "¿Me pueden mandar los horarios de clases por WhatsApp?"
    ]
  },
  professional: {
    label: "Servicios profesionales",
    vibe: "Quiet law-firm gravitas: warm paper white, deep ink-navy, steel-slate accents and a faint pinstripe texture — trustworthy stationery, not SaaS cobalt.",
    palette: {
      bg: "#F7F6F2",
      surface: "#FFFFFF",
      ink: "#1C2431",
      inkSoft: "#4E5A6B",
      accent: "#2F4A63",
      accentDark: "#24384B",
      onAccent: "#FFFFFF",
      cardBg: "#16202E",
      cardInk: "#F2F4F7",
      rule: "#D6D2C6"
    },
    fontCss: "https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@600;700&family=Public+Sans:wght@400;500;600&display=swap",
    displayFamily: "'Source Serif 4', Georgia, 'Times New Roman', serif",
    bodyFamily: "'Public Sans', 'Segoe UI', Helvetica, Arial, sans-serif",
    motif: "lines",
    questions_es: [
      "Quisiera agendar una cita para una consulta, ¿tienen espacio esta semana?",
      "¿Qué documentos necesito y cómo manejan los honorarios de la primera consulta?",
      "¿Me pueden mandar los detalles por WhatsApp para revisarlos con calma?"
    ]
  }
};

/* Resolve a template by key; unknown or missing keys get 'professional'. */
function elyonTemplate(key) {
  return ELYON_TEMPLATES[key] || ELYON_TEMPLATES.professional;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { ELYON_TEMPLATES: ELYON_TEMPLATES, elyonTemplate: elyonTemplate };
}
