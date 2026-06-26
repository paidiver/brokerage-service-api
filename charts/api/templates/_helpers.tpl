{{- define "brokerage-service-api.name" -}}
brokerage-service-api
{{- end }}

{{- define "brokerage-service-api.fullname" -}}
{{- if contains (include "brokerage-service-api.name" .) .Release.Name -}}
{{ .Release.Name }}
{{- else -}}
{{ printf "%s-%s" .Release.Name (include "brokerage-service-api.name" .) }}
{{- end -}}
{{- end }}
