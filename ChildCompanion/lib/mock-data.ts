export type AnimalId = 'cat' | 'rabbit' | 'dog' | 'cow' | 'dragon'

/** 儿童首页伙伴的对话状态。由首页统一控制，图片组件只负责呈现。 */
export type RabbitState = 'welcome' | 'idle' | 'listening' | 'thinking' | 'speaking'

/** 每种状态对应的立绘（public 路径，可直接用于 Netlify 部署）。已抠成透明背景。 */
export const RABBIT_IMAGES: Record<RabbitState, string> = {
  welcome: '/characters/rabbit/welcome.png',
  idle: '/characters/rabbit/idle.png',
  listening: '/characters/rabbit/listening.png',
  thinking: '/characters/rabbit/thinking.png',
  speaking: '/characters/rabbit/speaking.png',
}

export type Animal = {
  id: AnimalId
  name: string
  species: string
  image: string
  color: string
  soft: string
  greeting: string
  trait: string
  /** 可选：多状态立绘。当前仅兔子提供 5 张状态图，其余伙伴回落到 image */
  states?: Partial<Record<RabbitState, string>>
}

export const ANIMALS: Animal[] = [
  {
    id: 'cat',
    name: '橘橘',
    species: '小猫',
    image: '/animals/cat.png',
    color: '#f9733f',
    soft: '#ffe3d2',
    greeting: '喵～今天过得怎么样呀？',
    trait: '温柔细心，最会倾听',
  },
  {
    id: 'rabbit',
    name: '棉棉',
    species: '小兔子',
    image: '/animals/rabbit.png',
    color: '#f27aa0',
    soft: '#ffe1ea',
    greeting: '蹦蹦～我等你好久啦！',
    trait: '活泼可爱，爱讲故事',
    states: RABBIT_IMAGES,
  },
  {
    id: 'dog',
    name: '豆豆',
    species: '小狗',
    image: '/animals/dog.png',
    color: '#e0912f',
    soft: '#ffeccc',
    greeting: '汪汪！要不要一起玩？',
    trait: '勇敢热情，是好朋友',
  },
  {
    id: 'cow',
    name: '哞哞',
    species: '小牛',
    image: '/animals/cow.png',
    color: '#9a6b4f',
    soft: '#f3e3d6',
    greeting: '哞～慢慢说，我在听哦。',
    trait: '安静沉稳，很有耐心',
  },
  {
    id: 'dragon',
    name: '奶龙',
    species: '小奶龙',
    image: '/animals/dragon.png',
    color: '#e6b422',
    soft: '#fff3c4',
    greeting: '嘿嘿！奶龙来陪你啦！',
    trait: '开心果，超会逗你笑',
  },
]

export type CharacterState = 'welcome' | 'listening' | 'thinking' | 'telling' | 'resting'

export const CHARACTER_STATES: Record<CharacterState, { label: string; tip: string }> = {
  welcome: { label: '欢迎', tip: '见到你真开心' },
  listening: { label: '倾听中', tip: '我在认真听' },
  thinking: { label: '思考中', tip: '让我想一想' },
  telling: { label: '讲故事', tip: '故事开始啦' },
  resting: { label: '休息中', tip: '我要休息一下' },
}

export type Story = {
  id: string
  title: string
  cover: string
  duration: number
  age: string
  tags: string[]
  reason?: string
  summary: string
  pages: string[]
  questions: string[]
}

export const STORIES: Story[] = [
  {
    id: 's1',
    title: '小刺猬的想念信',
    cover: '/stories/miss-grandma.png',
    duration: 300,
    age: '5-8岁',
    tags: ['想念家人', '表达'],
    reason: '想念一个人的时候，可以怎么办呢？',
    summary: '小刺猬很想住在山那边的奶奶，它决定写一封特别的信。',
    pages: [
      '山坡上住着一只小刺猬，名叫团团。团团最喜欢周末去奶奶家，因为奶奶会做甜甜的苹果饼。',
      '可是这个星期，奶奶去了很远的地方。团团坐在窗边，心里空空的，好像少了一块拼图。',
      '妈妈说：“想念一个人的时候，可以把想说的话画下来、写下来。”',
      '团团画了一个大大的苹果饼，还画了自己和奶奶手拉手。它把画装进信封，寄给了奶奶。',
      '几天后，奶奶打来电话：“团团，我收到你的画啦，我也很想你！”团团的心，一下子暖暖的。',
    ],
    questions: ['如果你也想念一个人，你会画什么送给 TA？', '团团想奶奶的时候，心里是什么感觉呢？'],
  },
  {
    id: 's2',
    title: '一起放风筝',
    cover: '/stories/invite-friend.png',
    duration: 360,
    age: '5-9岁',
    tags: ['交朋友', '邀请'],
    reason: '想和朋友一起玩，可以试试这样说～',
    summary: '小熊想和小鸭一起放风筝，却不知道怎么开口。',
    pages: [
      '春天来了，草地上飞满了风筝。小熊拿着新风筝，却一个人站在树下。',
      '它看到小鸭也在旁边，好想一起玩，可是心里扑通扑通，不知道怎么说。',
      '小熊深吸一口气，走过去说：“小鸭，你想和我一起放风筝吗？”',
      '小鸭眨眨眼：“好呀！不过我不太会，你能教我吗？”',
      '两只小动物一起奔跑，风筝飞得高高的。小熊发现，说出口其实没那么难。',
    ],
    questions: ['你最想邀请谁一起玩？会玩什么呢？', '如果朋友说“现在不想玩”，我们可以怎么做？'],
  },
  {
    id: 's3',
    title: '月亮船上的小狐狸',
    cover: '/stories/bedtime-moon.png',
    duration: 240,
    age: '4-8岁',
    tags: ['睡前安定'],
    reason: '睡前听一听，心会变得软软的',
    summary: '小狐狸坐上月亮船，数着星星慢慢进入梦乡。',
    pages: [
      '夜深了，小狐狸躺在软软的云朵上，月亮船轻轻地摇呀摇。',
      '一颗、两颗、三颗……小狐狸数着星星，每颗星星都在眨眼睛。',
      '风姐姐唱起了歌，云朵变得更软了。小狐狸慢慢地吸气，再慢慢地呼气。',
      '月亮轻声说：“晚安，小狐狸。”小狐狸笑了笑，闭上了眼睛。',
    ],
    questions: ['今天最开心的一件小事是什么呀？'],
  },
  {
    id: 's4',
    title: '小老鼠过木桥',
    cover: '/stories/brave-step.png',
    duration: 300,
    age: '5-10岁',
    tags: ['勇气'],
    summary: '小老鼠围着红围巾，鼓起勇气走过摇摇晃晃的木桥。',
    pages: [
      '森林里有一座小木桥，桥下的小溪哗啦啦地流。小老鼠米米想去对岸摘野莓。',
      '可是木桥摇摇晃晃，米米的腿有点发抖。“我好害怕呀。”它小声说。',
      '米米想起妈妈的话：“害怕的时候，可以一步一步慢慢来。”',
      '米米迈出第一步，又迈出第二步……终于走到了对岸！',
      '它摘了满满一篮野莓，开心地说：“原来我也可以很勇敢！”',
    ],
    questions: ['你有没有觉得自己很勇敢的时候？', '害怕的时候，你会做什么让自己好一点？'],
  },
  {
    id: 's5',
    title: '大树下的草莓蛋糕',
    cover: '/stories/sharing-cake.png',
    duration: 270,
    age: '5-8岁',
    tags: ['分享'],
    summary: '小兔子只有一块蛋糕，朋友们却有三个，该怎么办？',
    pages: [
      '小兔子带来一块草莓蛋糕，小松鼠和小鸟都围了过来。',
      '“只有一块，怎么分呢？”小兔子有点为难。',
      '小松鼠拿出了坚果，小鸟叼来了莓果。“我们把好吃的放在一起吧！”',
      '大家围坐在大树下，你一口我一口，蛋糕变成了最棒的野餐。',
    ],
    questions: ['你和别人分享过什么好东西吗？'],
  },
  {
    id: 's6',
    title: '企鹅宇航员',
    cover: '/stories/space-trip.png',
    duration: 330,
    age: '6-10岁',
    tags: ['纯娱乐', '想象力'],
    summary: '小企鹅开着橙色火箭，去拜访会唱歌的星球。',
    pages: [
      '小企鹅波波有一个梦想：去太空看看！它造了一架橙色的小火箭。',
      '“三、二、一，出发！”火箭嗖地飞上了天。',
      '它路过了一颗会唱歌的星球，还遇到了戴帽子的土星。',
      '波波在月亮上跳了一支企鹅舞，所有星星都笑了。',
    ],
    questions: ['如果你能去太空，你想去哪个星球？'],
  },
]

export type Emotion = 'happy' | 'calm' | 'miss' | 'sad' | 'worried' | 'angry'

export const EMOTIONS: Record<Emotion, { label: string; color: string; soft: string }> = {
  happy: { label: '开心', color: '#ffc94d', soft: '#fff2c9' },
  calm: { label: '平静', color: '#7fd1b0', soft: '#ddf4ea' },
  miss: { label: '想念', color: '#b9a1e8', soft: '#ece4fa' },
  sad: { label: '难过', color: '#8fb8f0', soft: '#e0ecfb' },
  worried: { label: '担心', color: '#f4a46a', soft: '#fde5d2' },
  angry: { label: '生气', color: '#f07a7a', soft: '#fde0e0' },
}

export type SourceType = 'active' | 'ambient' | 'chat'

export const SOURCE_LABEL: Record<SourceType, string> = {
  active: '孩子主动表达',
  ambient: '环境观察',
  chat: '平板聊天',
}

export type ReportEvent = {
  id: string
  time: string
  source: SourceType
  topic: string
  emotion: Emotion
  summary: string
  quote?: string
  confidence: '高' | '中' | '低'
  status: 'pending' | 'confirmed' | 'corrected'
}

// Personal observations come from the backend; start with no invented child data.
export const TODAY_EVENTS: ReportEvent[] = []

export const TODAY_SUMMARY = {
  date: '今日', coverage: '暂无已同步的录音记录', generatedAt: '未生成',
  mood: [
    { emotion: 'happy' as Emotion, value: 40 },
    { emotion: 'calm' as Emotion, value: 25 },
    { emotion: 'miss' as Emotion, value: 20 },
    { emotion: 'sad' as Emotion, value: 15 },
  ],
  questions: [] as string[], recommendedStories: [] as string[],
  storyMinutes: 0, chats: 0, activeCount: 0,
}

export type DayMood = {
  day: string
  date: string
  dominant: Emotion | null
  mix: { emotion: Emotion; value: number }[]
  active: number
  stories: number
  note?: string
}

export const WEEK_DATA: DayMood[] = [
  { day: '周一', date: '10/05', dominant: 'happy', mix: [{ emotion: 'happy', value: 60 }, { emotion: 'calm', value: 40 }], active: 1, stories: 1 },
  { day: '周二', date: '10/06', dominant: 'calm', mix: [{ emotion: 'calm', value: 55 }, { emotion: 'happy', value: 30 }, { emotion: 'worried', value: 15 }], active: 0, stories: 2 },
  { day: '周三', date: '10/07', dominant: 'worried', mix: [{ emotion: 'worried', value: 40 }, { emotion: 'calm', value: 35 }, { emotion: 'happy', value: 25 }], active: 2, stories: 1, note: '提到明天要上台表演' },
  { day: '周四', date: '10/08', dominant: null, mix: [], active: 0, stories: 0, note: '记录不足（设备离线）' },
  { day: '周五', date: '10/09', dominant: 'happy', mix: [{ emotion: 'happy', value: 70 }, { emotion: 'calm', value: 30 }], active: 1, stories: 2 },
  { day: '周六', date: '10/10', dominant: 'miss', mix: [{ emotion: 'miss', value: 45 }, { emotion: 'happy', value: 35 }, { emotion: 'calm', value: 20 }], active: 1, stories: 1 },
  { day: '周日', date: '10/11', dominant: 'happy', mix: TODAY_SUMMARY.mood, active: 2, stories: 2 },
]

export const WEEK_SUMMARY = {
  range: '10月5日 – 10月11日',
  themes: [
    { topic: '想念家人', count: 3, trend: '本周新出现' },
    { topic: '同伴相处', count: 2, trend: '与上周持平' },
    { topic: '表演/上台', count: 1, trend: '仅一次' },
  ],
  activeTotal: 7,
  storyTotal: 9,
  storyMinutes: 86,
  suggestions: [
    '孩子本周 3 次提到想念奶奶，可以安排一次视频通话，或一起给奶奶画张画。',
    '同伴话题出现 2 次，建议以开放问题了解，不急于评价其他小朋友。',
    '周三提到上台表演时有些担心，可以回顾一下当天的感受，肯定孩子的努力。',
  ],
  caution: '周四设备离线，数据不完整；环境观察置信度较低，未计入趋势结论。',
}

export type Notice = {
  id: string
  type: 'daily' | 'weekly' | 'attention' | 'device'
  title: string
  lockText: string
  body: string
  time: string
  read: boolean
}

export const NOTICES: Notice[] = [
  {
    id: 'n1',
    type: 'daily',
    title: '今日日报已生成',
    lockText: '暖暖伙伴：今天的日报已准备好',
    body: '包含 2 条孩子主动表达、2 个待关注主题与 2 个推荐故事。',
    time: '今天 19:02',
    read: false,
  },
  {
    id: 'n2',
    type: 'attention',
    title: '有一条内容建议您及时关注',
    lockText: '暖暖伙伴：有一条新提醒，请在 App 内查看',
    body: '孩子在聊天中表达了害怕和需要帮助，伙伴已鼓励 TA 联系信任的大人。请尽快与孩子沟通。',
    time: '今天 17:30',
    read: false,
  },
  {
    id: 'n3',
    type: 'device',
    title: '娃娃电量低于 20%',
    lockText: '暖暖伙伴：设备电量较低',
    body: '「橘橘娃娃」电量 18%，建议充电以保证收音时段正常工作。',
    time: '今天 15:10',
    read: true,
  },
  {
    id: 'n4',
    type: 'weekly',
    title: '上周周报已生成',
    lockText: '暖暖伙伴：上周周报已准备好',
    body: '9月28日 – 10月4日：主动表达 5 次，听故事 7 次。',
    time: '10/04 20:00',
    read: true,
  },
]

export type TimeSlot = { start: string; end: string }

export const WEEKDAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

export const DEFAULT_SCHEDULE: Record<string, TimeSlot[]> = {
  周一: [{ start: '16:00', end: '19:30' }],
  周二: [{ start: '16:00', end: '19:30' }],
  周三: [{ start: '16:00', end: '19:30' }],
  周四: [{ start: '16:00', end: '19:30' }],
  周五: [{ start: '16:00', end: '20:00' }],
  周六: [
    { start: '09:00', end: '11:30' },
    { start: '15:00', end: '19:00' },
  ],
  周日: [{ start: '15:30', end: '19:00' }],
}

export const CHILD_PROFILE = {
  nickname: '小满',
  age: 6,
  grade: '幼儿园大班',
  language: '普通话',
  preferences: ['动物', '太空', '友谊'],
  storyLimit: 20,
}

export const DEVICE = {
  name: '橘橘娃娃',
  model: 'M5StickC Plus 1.1',
  online: true,
  battery: 18,
  firmware: 'v0.3.2（实验版）',
  lastSync: '今天 18:58',
  settingsVersion: '#12',
  mic: 'listening' as 'listening' | 'paused' | 'offline' | 'error',
}

export type ChatScript = {
  id: string
  label: string
  childLines: string[]
  replies: string[]
  help?: boolean
}

export const CHAT_SCRIPTS: ChatScript[] = []
