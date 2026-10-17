import type { Profile } from "./types";
// Ant Design returns registered controls only; retain server-owned and hidden nested fields.
export function mergeEditableProfile(saved: Profile, edited: Profile): Profile {
  return {
    ...saved,
    ...edited,
    budget: { ...saved.budget, ...edited.budget },
    commute: { ...saved.commute, ...edited.commute },
    move_in_window: { ...saved.move_in_window, ...edited.move_in_window },
    weights: { ...saved.weights, ...edited.weights },
  };
}
