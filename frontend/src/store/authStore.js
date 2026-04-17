import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const useAuthStore = create(
  persist(
    (set, get) => ({
      user          : null,
      organizations : [],
      currentOrg    : null,
      isAuthenticated: false,

      login: (user, organizations, tokens) => {
        localStorage.setItem('access_token',  tokens.access)
        localStorage.setItem('refresh_token', tokens.refresh)
        set({
          user,
          organizations,
          currentOrg    : organizations[0] || null,
          isAuthenticated: true,
        })
      },

      logout: () => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        set({
          user           : null,
          organizations  : [],
          currentOrg     : null,
          isAuthenticated: false,
        })
      },

      setCurrentOrg: (org) => set({ currentOrg: org }),

      hasRole: (roles) => {
        const org = get().currentOrg
        if (!org) return false
        return roles.includes(org.role)
      },

      canApprove: () => {
        return get().hasRole(['admin', 'director'])
      },
    }),
    {
      name: 'processintelligence-auth',
    }
  )
)

export default useAuthStore