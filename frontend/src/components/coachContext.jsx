// Shared Coach state (kept out of the .jsx files so they only export components).
import { createContext, useContext } from 'react'

export const CoachContext = createContext({
  open: false,
  openCoach: () => {},
  closeCoach: () => {},
  registerContext: () => () => {},
})

export const useCoach = () => useContext(CoachContext)

// Tools after which the plan / tasks / streak on screen are out of date.
export const PLAN_TOOLS = ['create_study_plan', 'complete_task']
export const PLAN_CHANGED_EVENT = 'coach:plan-changed'
