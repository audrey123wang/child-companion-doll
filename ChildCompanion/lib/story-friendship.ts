/**
 * 预置故事：《小熊阿团今天和别人玩了》
 *
 * 本轮为黑客松阶段，故事内容直接作为前端本地预置数据，
 * 不依赖后端接口。后续接入真实故事库时，保持相同的数据结构即可平滑替换。
 */

export type StoryScene = {
  /** 场景序号，从 1 开始 */
  index: number
  /** 本幕小标题 */
  title: string
  /** 本幕正文，段落用 \n\n 分隔 */
  text: string
  /** 插画路径（public 下的静态资源，Netlify 可直接访问） */
  image: string
  /** 预先生成并保存在 public 下的故事录音 */
  audio: string
}

export type Story = {
  id: string
  title: string
  scenes: StoryScene[]
}

export const FRIENDSHIP_STORY: Story = {
  id: 'friendship-bear',
  title: '小熊阿团今天和别人玩了',
  scenes: [
    {
      index: 1,
      title: '今天不一样',
      text: `小狐狸朵朵每天放学后，都喜欢和小熊阿团一起在树下玩。

可是今天，朵朵跑到树下时，却看见阿团正和小松鼠可可一起玩。

他们正在把一堆树叶堆成一座很高很高的山。

阿团没有像平时那样跑过来叫她。

朵朵心里有一点闷闷的。

她想：
“阿团今天是不是不想和我玩了？”`,
      image: '/stories/friendship/scene-1.png',
      audio: '/stories/friendship/audio/scene-1.mp3',
    },
    {
      index: 2,
      title: '越想越不开心',
      text: `朵朵一个人走到小溪边。

她踢了踢脚边的小石头。

她又想到：
“是不是因为可可比我更有趣？”
“是不是以后阿团都不跟我玩了？”

想着想着，她的尾巴都垂了下来。

这时候，一片树叶正好飘到她的鼻子上。

朵朵突然想到：

“等等……我其实还没有问过阿团呀。”`,
      image: '/stories/friendship/scene-2.png',
      audio: '/stories/friendship/audio/scene-2.mp3',
    },
    {
      index: 3,
      title: '去问一问',
      text: `朵朵重新跑回树下。

她没有生气，只是问：

“阿团，你们在玩什么呀？”

阿团抬起头，开心地说：

“我们在堆一座森林里最高的树叶山！”

朵朵又问：

“我可以一起玩吗？”

于是三个小伙伴一起开始堆树叶山。

朵朵发现，
有时候去问一问，
事情可能和自己想的不一样。`,
      image: '/stories/friendship/scene-3.png',
      audio: '/stories/friendship/audio/scene-3.mp3',
    },
    {
      index: 4,
      title: '朋友也可以和别人一起玩',
      text: `玩了一会儿，阿团说：

“等一下我还想和可可去找松果，因为我们刚才约好了。”

朵朵停了一下。

这一次，她没有马上想：
“阿团是不是不要我了？”

她说：

“好呀，那我去小溪边找几块漂亮的石头。”

阿团笑着说：

“好！”

朵朵发现：

朋友有时候会和别人一起玩。

这并不一定代表谁不喜欢谁。

如果不知道发生了什么，可以先问一问。

如果这一次没有一起玩，也可以去做自己喜欢的事。`,
      image: '/stories/friendship/scene-4.png',
      audio: '/stories/friendship/audio/scene-4.mp3',
    },
  ],
}
