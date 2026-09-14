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

{{- define "brokerage-service-api.redisUrl" -}}
{{- if not (has .Values.redis.backend (list "fake" "redis")) -}}
{{- fail "redis.backend must be fake or redis" -}}
{{- end -}}
{{- if .Values.redis.enabled -}}
{{- if ne .Values.redis.backend "redis" -}}
{{- fail "redis.enabled requires redis.backend=redis" -}}
{{- end -}}
{{- printf "redis://%s-redis:6379/0" (include "brokerage-service-api.fullname" . | trunc 57 | trimSuffix "-") -}}
{{- else if eq .Values.redis.backend "redis" -}}
{{- required "redis.url is required for external Redis" .Values.redis.url -}}
{{- else -}}
{{- .Values.redis.url -}}
{{- end -}}
{{- end -}}
