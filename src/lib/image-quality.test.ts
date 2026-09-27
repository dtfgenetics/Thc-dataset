import { describe, expect, it } from 'vitest'
import { assessImagePixels } from './image-quality'

function solid(value:number,width=20,height=20){
  const data=new Uint8ClampedArray(width*height*4)
  for(let i=0;i<data.length;i+=4){data[i]=value;data[i+1]=value;data[i+2]=value;data[i+3]=255}
  return{data,width,height}
}

describe('Grow Doc image quality preflight',()=>{
  it('flags very dark intake photos',()=>{
    const {data,width,height}=solid(10)
    const result=assessImagePixels(data,width,height)
    expect(result.metrics.meanLuminance).toBeLessThan(45)
    expect(result.notes.join(' ')).toMatch(/very dark/i)
  })

  it('flags blown-out intake photos',()=>{
    const {data,width,height}=solid(252)
    const result=assessImagePixels(data,width,height)
    expect(result.metrics.highlightClipPercent).toBeGreaterThan(15)
    expect(result.notes.join(' ')).toMatch(/bright|glare|overexposure/i)
  })

  it('recognizes stronger edge detail in a checkerboard than a flat image',()=>{
    const width=20,height=20
    const data=new Uint8ClampedArray(width*height*4)
    for(let y=0;y<height;y++)for(let x=0;x<width;x++){
      const v=(x+y)%2===0?25:230
      const i=(y*width+x)*4
      data[i]=v;data[i+1]=v;data[i+2]=v;data[i+3]=255
    }
    const textured=assessImagePixels(data,width,height)
    const flat=solid(128,width,height)
    const smooth=assessImagePixels(flat.data,width,height)
    expect(textured.metrics.edgeEnergy).toBeGreaterThan(smooth.metrics.edgeEnergy)
    expect(smooth.notes.join(' ')).toMatch(/edge detail/i)
  })
})
