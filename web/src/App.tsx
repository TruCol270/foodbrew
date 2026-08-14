import { Link, Route, Routes } from 'react-router-dom'

import FormulationSetup from './screens/FormulationSetup'
import Home from './screens/Home'
import RecipeBuilder from './screens/RecipeBuilder'
import Verdict from './screens/Verdict'

export default function App() {
  return (
    <div className="app">
      <header>
        <Link to="/" className="brand">FoodBrew</Link>
        <nav>
          <Link to="/recipes/new">New recipe</Link>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/recipes/new" element={<RecipeBuilder />} />
          <Route path="/recipes/:recipeId" element={<RecipeBuilder />} />
          <Route path="/recipes/:recipeId/formulation" element={<FormulationSetup />} />
          <Route path="/evaluations/:evaluationId" element={<Verdict />} />
        </Routes>
      </main>
      <footer>
        Formulation decision support. Not a safety, efficacy, or regulatory determination.
      </footer>
    </div>
  )
}
