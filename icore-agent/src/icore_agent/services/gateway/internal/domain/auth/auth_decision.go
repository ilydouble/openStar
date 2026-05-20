package auth

const (
	// AuthResultPublic marks routes that do not require bearer authentication.
	AuthResultPublic = "public"
	// AuthResultSuccess marks requests with a valid gateway JWT.
	AuthResultSuccess = "success"
	// AuthResultMissingToken marks protected requests without a bearer token.
	AuthResultMissingToken = "missing_token"
	// AuthResultInvalidToken marks protected requests with an invalid bearer token.
	AuthResultInvalidToken = "invalid_token"
)
