{{- define "annotations-api.name" -}}
annotations-api
{{- end }}

{{- define "annotations-api.fullname" -}}
{{ printf "%s-%s" .Release.Name (include "annotations-api.name" .) }}
{{- end }}