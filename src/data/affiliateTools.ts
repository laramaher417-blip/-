export interface ToolAffiliateConfig {
  id: string;
  name: string;
  /** الرابط التسويقي (يُضاف عند الاعتماد من PartnerStack أو الشبكة) */
  affiliateUrl?: string;
  /** الرابط المباشر الرسمي كبديل أو للأدوات غير المتاحة كأفلييت مثل Notion */
  directUrl: string;
  /** يُفعّل true فقط عندما يكون الرابط رابط أفلييت مدفوعاً/ممولاً */
  isSponsored: boolean;
  /** حالة الاعتماد للمتابعة التنظيمية */
  status: 'approved' | 'pending' | 'no-program' | 'direct-only';
  /** ملاحظات إضافية اختيارية */
  notes?: string;
}

export const AFFILIATE_TOOLS: Record<string, ToolAffiliateConfig> = {
  notion: {
    id: 'notion',
    name: 'Notion',
    affiliateUrl: undefined,
    directUrl: 'https://www.notion.so',
    isSponsored: false,
    status: 'no-program',
    notes: 'برنامج الأفلييت مغلق حالياً للمتقدمين الجدد؛ يُستخدم الرابط المباشر.',
  },
  monday: {
    id: 'monday',
    name: 'monday.com',
    affiliateUrl: undefined, // ضعي رابط الأفلييت هنا فور الموافقة
    directUrl: 'https://monday.com',
    isSponsored: false,
    status: 'pending',
    notes: 'تم التقديم عبر PartnerStack بانتظار الاعتماد.',
  },
  zapier: {
    id: 'zapier',
    name: 'Zapier',
    affiliateUrl: undefined, // ضعي رابط الأفلييت هنا فور الموافقة
    directUrl: 'https://zapier.com',
    isSponsored: false,
    status: 'pending',
    notes: 'تم التقديم عبر PartnerStack بانتظار الاعتماد.',
  },
  clickup: {
    id: 'clickup',
    name: 'ClickUp',
    affiliateUrl: undefined, // ضعي رابط الأفلييت هنا فور الموافقة
    directUrl: 'https://clickup.com',
    isSponsored: false,
    status: 'pending',
    notes: 'تم التقديم عبر PartnerStack بانتظار الاعتماد.',
  },
};

/** دالة مساعدة لإرجاع الرابط الفعّال وما إذا كان مدفوعاً */
export function resolveToolLink(toolKey: string): {
  href: string;
  isSponsoredLink: boolean;
  toolName: string;
} {
  const tool = AFFILIATE_TOOLS[toolKey];
  if (!tool) {
    return { href: '#', isSponsoredLink: false, toolName: toolKey };
  }

  const hasAffiliate = Boolean(tool.affiliateUrl && tool.affiliateUrl.trim() !== '');
  if (hasAffiliate && tool.isSponsored) {
    return {
      href: tool.affiliateUrl!.trim(),
      isSponsoredLink: true,
      toolName: tool.name,
    };
  }

  return {
    href: tool.directUrl,
    isSponsoredLink: false,
    toolName: tool.name,
  };
}
