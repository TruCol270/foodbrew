import { Link, Route, Routes } from 'react-router-dom'

import Compare from './screens/Compare'
import Database from './screens/Database'
import FormulationSetup from './screens/FormulationSetup'
import Home from './screens/Home'
import RecipeBuilder from './screens/RecipeBuilder'
import Report from './screens/Report'
import Verdict from './screens/Verdict'

export default function App() {
  return (
    <div className="app">
      <header>
        <Link to="/" className="brand">FoodBrew</Link>
        <nav>
          <Link to="/recipes/new">New recipe</Link>
          <Link to="/database">Database</Link>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/recipes/new" element={<RecipeBuilder />} />
          <Route path="/recipes/:recipeId" element={<RecipeBuilder />} />
          <Route path="/recipes/:recipeId/formulation" element={<FormulationSetup />} />
          <Route path="/evaluations/:evaluationId" element={<Verdict />} />
          <Route path="/evaluations/:evaluationId/report" element={<Report />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/database" element={<Database />} />
        </Routes>
      </main>
      <footer>
        Formulation decision support. Not a safety, efficacy, or regulatory determination.
      </footer>
    </div>
  )
}
