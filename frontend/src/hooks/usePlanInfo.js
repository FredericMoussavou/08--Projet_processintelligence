import { useQuery } from '@tanstack/react-query'
import { organizationsAPI } from '../services/api'

/**
 * Hook pour récupérer le plan d'une organisation.
 *
 * Utilise React Query pour :
 *   - Mettre en cache la réponse (stale time 5 min)
 *   - Éviter les refetch inutiles entre composants
 *   - Gérer loading / error automatiquement
 *
 * Usage :
 *   const { data, isLoading, error } = usePlanInfo(currentOrg?.id)
 *   if (isLoading) return <Spinner />
 *   const planId = data?.plan?.id   // 'free' | 'pro' | 'business'
 *
 * @param {number|undefined} orgId
 * @returns {object} React Query result { data, isLoading, error, refetch }
 */
export default function usePlanInfo(orgId) {
  return useQuery({
    queryKey: ['organization', orgId, 'plan'],
    queryFn: async () => {
      const response = await organizationsAPI.getPlan(orgId)
      return response.data
    },
    enabled: !!orgId,
    staleTime: 1000 * 60 * 5,   // 5 minutes
  })
}
