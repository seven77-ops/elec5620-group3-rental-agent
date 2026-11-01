type Locality = { suburb: string; state: string; postcode: string };

export function isLocalityQuery(query: string, item: Locality): boolean {
  const normalize = (value: string) =>
    value.replace(/[,，]/g, " ").replace(/\s+/g, " ").trim().toLowerCase();
  return [
    item.suburb,
    item.postcode,
    `${item.state} ${item.postcode}`,
    `${item.suburb} ${item.postcode}`,
    `${item.suburb} ${item.state}`,
    `${item.suburb} ${item.state} ${item.postcode}`,
  ].some((value) => normalize(value) === normalize(query));
}
