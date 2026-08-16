import type { AllergenDeclaration as Declaration } from '../api/types'

/** An empty declaration is a gap in the records, never a clearance (decision #2). */
export function AllergenDeclarationPanel({ declaration }: { declaration: Declaration }) {
  return (
    <section data-testid="allergens">
      <h3>Allergens</h3>
      {declaration.entries.length === 0 ? (
        <p>
          No allergen is recorded for any ingredient in this recipe. That is a gap in
          the ingredient records, not a statement that the product is free of allergens.
        </p>
      ) : (
        <table>
          <thead><tr><th>Allergen</th><th>From</th></tr></thead>
          <tbody>
            {declaration.entries.map((entry) => (
              <tr key={entry.allergen} data-testid={`allergen-${entry.allergen}`}>
                <th scope="row">{entry.text}</th>
                <td>{entry.from_food_names.join(', ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {declaration.unrecorded_food_names.length > 0 && (
        <p className="blurb" data-testid="allergens-unrecorded">
          Allergens are not recorded for: {declaration.unrecorded_food_names.join(', ')}.
          Fill these in before anyone relies on the declaration above.
        </p>
      )}
    </section>
  )
}
