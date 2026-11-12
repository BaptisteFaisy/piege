# Piège — variables d'entrée du plan de contrôle.
variable "environnement" {
  description = "Nom de l'environnement (demo, prod)."
  type        = string
  default     = "demo"
}

variable "region" {
  description = "Région AWS. eu-west-3 par défaut, repli eu-central-1 (chapitre 31, point 1)."
  type        = string
  default     = "eu-west-3"
}

variable "prefixe" {
  description = "Préfixe de nommage des ressources."
  type        = string
  default     = "piege"
}

variable "modele_juge" {
  description = "Identifiant du modèle Bedrock utilisé comme juge."
  type        = string
  default     = "modele-fort"
}
