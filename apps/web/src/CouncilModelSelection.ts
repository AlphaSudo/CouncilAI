import type { Dict } from "./types";

export function preferredCouncilProvider(boot: Dict) {
  return boot.providers.nebius_token_factory.ready ||
    boot.providers.nebius_token_factory.preferred
    ? "nebius_token_factory"
    : boot.providers.direct_council.ready
      ? "direct_council"
      : boot.providers.openrouter_free.enabled &&
          (boot.providers.openrouter_free.configured ||
            boot.providers.openrouter_free.ready)
        ? "openrouter_free"
        : "fixture";
}

export function defaultCouncilModels(boot: Dict, provider: string): string[] {
  const settings = boot.providers[provider];
  const available = settings.models.filter(
    (model: Dict) => model.configured !== false,
  );
  if (Array.isArray(settings.default_models)) {
    return settings.default_models.filter((id: string) =>
      available.some((model: Dict) => model.id === id),
    );
  }
  return available
    .slice(
      0,
      ["direct_council", "nebius_token_factory"].includes(provider) ? 4 : 3,
    )
    .map((model: Dict) => model.id);
}
