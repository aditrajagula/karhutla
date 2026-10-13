export type BoundaryCategory = 'administrative' | 'peatland' | 'forest';

export interface BoundaryFeature {
  id: string;
  name: string;
  category: BoundaryCategory;
  sourceAttribution: string;
  geometry: GeoJSON.Geometry;
}
