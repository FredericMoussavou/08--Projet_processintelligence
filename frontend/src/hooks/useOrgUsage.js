import { useQuery } from '@tanstack/react-query'
import { organizationsAPI } from '../services/api'

/**
 * Hook pour récupérer l'usage mensuel d'une organisation.
 *
 * Le staleTime est plus court que pour le plan (1 min au lieu de 5) parce que
 * les compteurs changent au fil de l'utilisation (nouvelles analyses, etc.).
 *
 * Usage :
 *   const { data, isLoading } = useOrgUsage(currentOrg?.id)
 *   const { count, limit, quota_reached } = data?.analyses || {}
 *
 * @param {number|undefined} orgId
 * @returns {object} React Query result
 */
export default function useOrgUsage(orgId) {
  return useQuery({
    queryKey: ['organization', orgId, 'usage'],
    queryFn: async () => {
      const response = await organizationsAPI.getUsage(orgId)
      return response.data
    },
    enabled: !!orgId,
    staleTime: 1000 * 60,   // 1 minute
  })
}
