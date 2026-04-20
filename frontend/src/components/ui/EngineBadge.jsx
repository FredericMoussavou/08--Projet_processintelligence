import { Sparkles, FileCode, Zap } from 'lucide-react'

/**
 * Badge indiquant le moteur d'analyse utilisé pour une procédure.
 *
 * Props :
 *   engine  : 'claude' | 'spacy' | 'csv'
 *   size    : 'sm' | 'md' (défaut 'md')
 *
 * Usage :
 *   <EngineBadge engine="claude" />
 *   <EngineBadge engine="spacy" size="sm" />
 */
export default function EngineBadge({ engine = 'spacy', size = 'md' }) {
  const config = {
    claude: {
      label: 'Analyse IA Premium',
      Icon: Sparkles,
      classes: 'bg-purple-50 text-purple-700 border-purple-200',
      title: "Analyse effectuée par l'IA Claude d'Anthropic",
    },
    spacy: {
      label: 'Analyse standard',
      Icon: Zap,
      classes: 'bg-gray-100 text-gray-700 border-gray-200',
      title: 'Analyse par règles linguistiques (spaCy)',
    },
    csv: {
      label: 'Import structuré',
      Icon: FileCode,
      classes: 'bg-blue-50 text-blue-700 border-blue-200',
      title: 'Données importées depuis un fichier CSV structuré',
    },
  }

  const engineConfig = config[engine] || config.spacy
  const { Icon } = engineConfig

  const sizeClasses =
    size === 'sm'
      ? 'text-xs px-2 py-0.5 gap-1'
      : 'text-sm px-3 py-1 gap-1.5'

  const iconSize = size === 'sm' ? 12 : 14

  return (
    <span
      title={engineConfig.title}
      className={`inline-flex items-center rounded-full border font-medium ${engineConfig.classes} ${sizeClasses}`}
    >
      <Icon size={iconSize} strokeWidth={2.5} />
      {engineConfig.label}
    </span>
  )
}
